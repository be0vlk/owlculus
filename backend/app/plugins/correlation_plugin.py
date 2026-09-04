"""
Plugin for scanning and correlating entity names across cases
"""

from collections.abc import AsyncGenerator
from typing import Any, Optional, get_origin

from sqlmodel import Session, select

from ..core.roles import UserRole
from ..core.utils import get_utc_now
from ..database.models import Case, CaseUserLink, Entity, User
from ..schemas.entity_schema import ENTITY_TYPE_SCHEMAS
from .base_plugin import BasePlugin, PluginRun, ResultEvent


class CorrelationScan(BasePlugin):
    """Plugin for finding matching entities across cases"""

    def __init__(self):
        super().__init__(display_name="Correlation Scan")
        self.description = "Finds matching entities and relationships across cases"
        self.category = "Other"
        self.evidence_category = "Documents"
        self.parameters = {
            "case_id": {
                "type": "integer",
                "description": "ID of the case to scan",
                "required": True,
            }
        }

    def _is_admin(self, user: User) -> bool:
        """Check if current user is an admin"""
        return user.role == UserRole.ADMIN

    def _build_accessible_entities_query(
        self,
        db: Session,
        user: User,
        exclude_entity_id: int | None = None,
        entity_type_filter: str | None = None,
    ):
        """Build a query for entities accessible to the current user"""
        query = select(Entity, Case).join(Case)
        filters = []
        if exclude_entity_id:
            filters.append(Entity.id != exclude_entity_id)
        if entity_type_filter:
            filters.append(Entity.entity_type == entity_type_filter)
        if not self._is_admin(user):
            query = query.join(CaseUserLink, Case.id == CaseUserLink.case_id)
            filters.append(CaseUserLink.user_id == user.id)
        if filters:
            query = query.where(*filters)
        return query

    def _parse_domain_from_string(self, input_string: str) -> str | None:
        """Extract domain from email or URL string"""
        if not input_string:
            return None
        if "@" in input_string:
            domain = input_string.split("@")[-1].lower()
            return domain if domain else None
        if input_string.startswith(("http://", "https://")):
            domain = input_string.replace("https://", "").replace("http://", "")
            domain = domain.split("/")[0].lower()
            return domain if domain else None
        return None

    def _extract_domains_from_entity(self, entity: Entity) -> list[str]:
        """Extract all domains associated with an entity"""
        domains: list[str] = []
        if not entity.data:
            return domains
        if entity.entity_type == "domain":
            domain = entity.data.get("domain", "")
            if domain:
                domains.append(domain.lower())
        elif entity.entity_type == "person":
            usernames = entity.data.get("usernames", [])
            for username in usernames:
                domain = self._parse_domain_from_string(username)
                if domain:
                    domains.append(domain)
            email = entity.data.get("email", "")
            domain = self._parse_domain_from_string(email)
            if domain:
                domains.append(domain)
        elif entity.entity_type == "company":
            website = entity.data.get("website", "")
            domain = self._parse_domain_from_string(website)
            if domain:
                domains.append(domain)
        return list(set(domains))

    def _extract_vehicle_identifiers(self, entity: Entity) -> dict[str, str]:
        """Extract VIN and license plate from a vehicle entity"""
        identifiers: dict[str, str] = {}
        if not entity.data or entity.entity_type != "vehicle":
            return identifiers
        vin = entity.data.get("vin", "")
        if vin:
            identifiers["vin"] = vin.upper()
        license_plate = entity.data.get("license_plate", "")
        if license_plate:
            normalized_plate = license_plate.replace(" ", "").replace("-", "").upper()
            identifiers["license_plate"] = normalized_plate
        return identifiers

    def _create_match_dict(
        self, entity: Entity, case: Case, entity_name: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Create a standardized match dictionary"""
        match_dict = {
            "entity_id": entity.id,
            "entity_type": entity.entity_type,
            "case_id": entity.case_id,
            "case_number": case.case_number,
            "case_title": case.title,
        }
        if entity_name:
            match_dict["entity_name"] = entity_name
        match_dict.update(kwargs)
        return match_dict

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        if not params:
            yield self.error("Parameters are required")
            return
        async for result in self.execute(params, ctx.session, ctx.user):
            yield result

    async def execute(
        self, params: dict[str, Any], db: Session, user: User
    ) -> AsyncGenerator[ResultEvent, None]:
        try:
            case_id = params.get("case_id")
            if not case_id:
                yield self.error("Case ID is required")
                return
            if not self._is_admin(user):
                stmt = select(CaseUserLink).where(
                    CaseUserLink.case_id == case_id,
                    CaseUserLink.user_id == user.id,
                )
                result = db.execute(stmt)
                if not result.first():
                    yield self.error("You do not have access to this case")
                    return
            case_entities = await self._get_case_entities(db, case_id)
            reported_matches = set()
            for entity in case_entities:
                entity_name = self._get_display_name(entity.data, entity.entity_type)
                employer_name = None
                if entity.entity_type == "person" and entity.data:
                    employer_name = entity.data.get("employer", "")
                if not entity_name:
                    continue
                name_matches = []
                if entity.entity_type != "vehicle":
                    name_matches = await self._find_name_matches(
                        db, user, entity, entity_name
                    )
                if name_matches:
                    match_key = f"name:{entity.entity_type}:{entity_name.lower()}"
                    if match_key not in reported_matches:
                        reported_matches.add(match_key)
                        match_data = {
                            "entity_id": entity.id,
                            "entity_name": entity_name,
                            "entity_type": entity.entity_type,
                            "match_type": "name",
                            "case_id": case_id,
                            "matches": name_matches,
                        }
                        yield self.data(match_data)
                if employer_name:
                    employer_matches = await self._find_employer_matches(
                        db, user, entity, employer_name
                    )
                    if employer_matches:
                        match_key = f"employer:{employer_name.lower()}"
                        if match_key not in reported_matches:
                            reported_matches.add(match_key)
                            match_data = {
                                "entity_id": entity.id,
                                "entity_name": entity_name,
                                "entity_type": entity.entity_type,
                                "match_type": "employer",
                                "employer_name": employer_name,
                                "case_id": case_id,
                                "matches": employer_matches,
                            }
                            yield self.data(match_data)
                if entity.entity_type != "domain":
                    domain_matches = await self._find_domain_matches(db, user, entity)
                    if domain_matches:
                        for domain, matches in domain_matches.items():
                            match_key = f"domain:{domain.lower()}"
                            if match_key not in reported_matches:
                                reported_matches.add(match_key)
                                match_data = {
                                    "entity_id": entity.id,
                                    "entity_name": entity_name,
                                    "entity_type": entity.entity_type,
                                    "match_type": "domain",
                                    "domain": domain,
                                    "case_id": case_id,
                                    "matches": matches,
                                }
                                yield self.data(match_data)
                if entity.entity_type == "vehicle":
                    vehicle_matches = await self._find_vehicle_matches(db, user, entity)
                    if vehicle_matches:
                        for identifier_type, matches in vehicle_matches.items():
                            matched_value = matches[0].get("matched_value", "")
                            match_key = f"{identifier_type}:{matched_value.lower()}"
                            if match_key not in reported_matches:
                                reported_matches.add(match_key)
                                match_data = {
                                    "entity_id": entity.id,
                                    "entity_name": entity_name,
                                    "entity_type": entity.entity_type,
                                    "match_type": identifier_type,
                                    "matched_value": matched_value,
                                    "case_id": case_id,
                                    "matches": matches,
                                }
                                yield self.data(match_data)
        except Exception as e:
            yield self.error(f"Error during correlation scan: {e!s}")

    async def _get_case_entities(self, db: Session, case_id: int) -> list[Entity]:
        """Get all entities for a specific case"""
        stmt = select(Entity).where(Entity.case_id == case_id)
        result = db.execute(stmt)
        return result.scalars().all()

    async def _find_name_matches(
        self, db: Session, user: User, source_entity: Entity, entity_name: str
    ) -> list[dict[str, Any]]:
        """Find entities with matching names across all cases assigned to the current user"""
        stmt = self._build_accessible_entities_query(
            db,
            user,
            exclude_entity_id=source_entity.id,
            entity_type_filter=source_entity.entity_type,
        )
        result = db.execute(stmt)
        matches = []
        normalized_source_name = entity_name.lower()
        for entity, case in result:
            match_name = self._get_display_name(entity.data, entity.entity_type)
            if match_name and match_name.lower() == normalized_source_name:
                matches.append(self._create_match_dict(entity, case))
        return matches

    async def _find_employer_matches(
        self, db: Session, user: User, source_entity: Entity, employer_name: str
    ) -> list[dict[str, Any]]:
        """Find entities with matching employer names across all cases assigned to the current user"""
        stmt = self._build_accessible_entities_query(
            db, user, exclude_entity_id=source_entity.id, entity_type_filter="person"
        )
        result = db.execute(stmt)
        matches = []
        normalized_employer = employer_name.lower()
        for entity, case in result:
            if (
                entity.data
                and entity.data.get("employer", "").lower() == normalized_employer
            ):
                person_name = self._get_display_name(entity.data, "person")
                matches.append(
                    self._create_match_dict(entity, case, person_name=person_name)
                )
        return matches

    async def _find_domain_matches(
        self, db: Session, user: User, source_entity: Entity
    ) -> dict[str, list[dict[str, Any]]]:
        """Find entities with matching domains across all cases assigned to the current user"""
        domains_to_check = self._extract_domains_from_entity(source_entity)
        if not domains_to_check:
            return {}
        all_matches: dict[str, list[dict[str, Any]]] = {}
        for domain in domains_to_check:
            matches = await self._find_entities_with_domain(
                db, user, source_entity, domain
            )
            if matches:
                all_matches[domain] = matches
        return all_matches

    async def _find_entities_with_domain(
        self, db: Session, user: User, source_entity: Entity, domain: str
    ) -> list[dict[str, Any]]:
        """Find all entities that contain the specified domain"""
        stmt = self._build_accessible_entities_query(
            db, user, exclude_entity_id=source_entity.id
        )
        result = db.execute(stmt)
        matches = []
        normalized_domain = domain.lower()
        for entity, case in result:
            found_in = []
            entity_domains = self._extract_domains_from_entity(entity)
            if normalized_domain in entity_domains:
                if entity.entity_type == "domain" and entity.data:
                    if entity.data.get("domain", "").lower() == normalized_domain:
                        found_in.append("domain field")
                elif entity.entity_type == "person" and entity.data:
                    usernames = entity.data.get("usernames", [])
                    for username in usernames:
                        if (
                            "@" in username
                            and username.split("@")[-1].lower() == normalized_domain
                        ):
                            found_in.append(f"username: {username}")
                    email = entity.data.get("email", "")
                    if (
                        email
                        and "@" in email
                        and (email.split("@")[-1].lower() == normalized_domain)
                    ):
                        found_in.append(f"email: {email}")
                elif entity.entity_type == "company" and entity.data:
                    website = entity.data.get("website", "")
                    if website:
                        parsed_domain = self._parse_domain_from_string(website)
                        if parsed_domain == normalized_domain:
                            found_in.append(f"website: {website}")
                if found_in:
                    entity_name = self._get_display_name(
                        entity.data, entity.entity_type
                    )
                    matches.append(
                        self._create_match_dict(
                            entity,
                            case,
                            entity_name=entity_name,
                            found_in=", ".join(found_in),
                        )
                    )
        return matches

    async def _find_vehicle_matches(
        self, db: Session, user: User, source_entity: Entity
    ) -> dict[str, list[dict[str, Any]]]:
        """Find entities with matching VIN or license plate across all cases assigned to the current user"""
        identifiers = self._extract_vehicle_identifiers(source_entity)
        if not identifiers:
            return {}
        stmt = self._build_accessible_entities_query(
            db, user, exclude_entity_id=source_entity.id, entity_type_filter="vehicle"
        )
        result = db.execute(stmt)
        all_matches: dict[str, list[dict[str, Any]]] = {}
        for entity, case in result:
            entity_identifiers = self._extract_vehicle_identifiers(entity)
            if "vin" in identifiers and "vin" in entity_identifiers:
                if identifiers["vin"] == entity_identifiers["vin"]:
                    if "vin" not in all_matches:
                        all_matches["vin"] = []
                    vehicle_name = self._get_display_name(entity.data, "vehicle")
                    all_matches["vin"].append(
                        self._create_match_dict(
                            entity,
                            case,
                            entity_name=vehicle_name,
                            matched_value=identifiers["vin"],
                        )
                    )
            if "license_plate" in identifiers and "license_plate" in entity_identifiers:
                if identifiers["license_plate"] == entity_identifiers["license_plate"]:
                    if "license_plate" not in all_matches:
                        all_matches["license_plate"] = []
                    vehicle_name = self._get_display_name(entity.data, "vehicle")
                    all_matches["license_plate"].append(
                        self._create_match_dict(
                            entity,
                            case,
                            entity_name=vehicle_name,
                            matched_value=entity.data.get("license_plate", ""),
                        )
                    )
        return all_matches

    def _get_primary_fields_for_entity(self, entity_type: str) -> list[str]:
        """Dynamically determine primary identifier fields for an entity type"""
        if entity_type not in ENTITY_TYPE_SCHEMAS:
            return []
        schema_class = ENTITY_TYPE_SCHEMAS[entity_type]
        annotations = getattr(schema_class, "__annotations__", {})
        required_fields = []
        name_like_fields = []
        for field_name, field_type in annotations.items():
            if get_origin(field_type) is not None:
                if get_origin(field_type) is type(Optional[str]):
                    continue
            if field_type == str:
                required_fields.append(field_name)
            if any(
                keyword in field_name.lower()
                for keyword in ["name", "domain", "ip", "address"]
            ):
                name_like_fields.append(field_name)
        if entity_type == "person":
            if "first_name" in annotations and "last_name" in annotations:
                return ["first_name", "last_name"]
        if entity_type == "vehicle":
            return ["year", "make", "model"]
        if required_fields:
            return required_fields
        if name_like_fields:
            return name_like_fields[:1]
        common_patterns = [entity_type, "name", "title", "identifier"]
        for pattern in common_patterns:
            if pattern in annotations:
                return [pattern]
        return []

    def _get_display_name(self, data: dict, entity_type: str) -> str:
        """Extract display name from entity data based on type"""
        if not data:
            return ""
        if entity_type not in ENTITY_TYPE_SCHEMAS:
            return data.get("Name", "")
        primary_fields = self._get_primary_fields_for_entity(entity_type)
        if not primary_fields:
            return data.get(entity_type, data.get("name", ""))
        field_values = []
        for field in primary_fields:
            value = data.get(field, "")
            if value:
                field_values.append(str(value))
        return " ".join(field_values).strip()

    def format_evidence(
        self, results: list[dict[str, Any]], params: dict[str, Any]
    ) -> str:
        """Custom formatting for correlation scan evidence"""
        if not results:
            return ""
        content_lines = [
            "Correlation Scan Results",
            "=" * 50,
            "",
            f"Total entities with matches: {len(results)}",
            f"Case ID: {params.get('case_id', 'Unknown')}",
            f"Execution time: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]
        for match_group in results:
            entity_name = match_group["entity_name"]
            entity_type = match_group["entity_type"]
            match_type = match_group.get("match_type", "name")
            matches = match_group["matches"]
            if match_type == "name":
                correlation_context = f"Found an entity named '{entity_name}' that appears in multiple cases. This may indicate the same {entity_type} is involved in different investigations."
            elif match_type == "employer":
                correlation_context = f"Found multiple people who work at '{match_group.get('employer_name', '')}'. This employer connection may indicate a relationship between these cases."
            elif match_type == "domain":
                correlation_context = f"Found multiple entities associated with the domain '{match_group.get('domain', '')}'. This domain connection may indicate a relationship between these cases or entities."
            elif match_type == "vin":
                correlation_context = f"Found multiple vehicles with the same VIN '{match_group.get('matched_value', '')}'. This indicates the same vehicle appears in multiple cases, which strongly suggests a connection between these investigations."
            elif match_type == "license_plate":
                correlation_context = f"Found multiple vehicles with the same license plate '{match_group.get('matched_value', '')}'. This indicates the same vehicle appears in multiple cases, suggesting a connection between these investigations."
            content_lines.extend(
                [
                    f"Entity: {entity_name}",
                    f"Type: {entity_type}",
                    f"Match Type: {match_type}",
                    "",
                    "Correlation Context:",
                    correlation_context,
                    "",
                ]
            )
            if match_type == "employer":
                content_lines.append(
                    f"Employer: {match_group.get('employer_name', '')}"
                )
            elif match_type == "domain":
                content_lines.append(f"Domain: {match_group.get('domain', '')}")
            elif match_type in ["vin", "license_plate"]:
                content_lines.append(
                    f"{('VIN' if match_type == 'vin' else 'License Plate')}: {match_group.get('matched_value', '')}"
                )
            content_lines.extend(["-" * 30, "", "Related Cases and Details:", ""])
            for match in matches:
                match_info = [
                    f"Case: {match['case_title']} (#{match['case_number']})",
                    f"Case ID: {match['case_id']}",
                ]
                if match_type == "employer":
                    match_info.extend(
                        [
                            f"Person: {match.get('person_name', '')}",
                            "Relationship: Works at the same employer",
                        ]
                    )
                elif match_type == "domain":
                    match_info.extend(
                        [
                            f"Found in: {match.get('found_in', '')}",
                            f"Relationship: Domain association ({match.get('entity_type', '')})",
                        ]
                    )
                elif match_type == "vin":
                    match_info.append("Relationship: Same vehicle (VIN match)")
                elif match_type == "license_plate":
                    match_info.append(
                        "Relationship: Same vehicle (license plate match)"
                    )
                else:
                    match_info.append(f"Relationship: Same {entity_type} name match")
                match_info.append("")
                content_lines.extend(match_info)
            content_lines.append("=" * 50 + "\n")
        return "\n".join(content_lines)
