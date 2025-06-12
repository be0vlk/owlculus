"""
Plugin for scanning and correlating entity names across cases
"""

from typing import Any, AsyncGenerator, Dict, List, Optional, get_args, get_origin

from sqlmodel import Session, select

from ..core.dependencies import get_db
from ..core.utils import get_utc_now
from ..database.models import Case, CaseUserLink, Entity
from ..schemas.entity_schema import ENTITY_TYPE_SCHEMAS
from .base_plugin import BasePlugin


class CorrelationScan(BasePlugin):
    """Plugin for finding matching entities across cases"""

    def __init__(self, db_session: Session = None):
        super().__init__(display_name="Correlation Scan", db_session=db_session)
        self.description = "Finds matching entities and relationships across cases"
        self.category = "Other"
        self.evidence_category = "Documents"
        self.save_to_case = False
        self.parameters = {
            "case_id": {
                "type": "integer",
                "description": "ID of the case to scan",
                "required": True,
            },
        }

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Not used as database queries are handled directly"""
        return None

    async def run(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not params:
            yield {"type": "error", "data": {"message": "Parameters are required"}}
            return

        # Use injected session if available, otherwise get a new one
        if self._db_session:
            db = self._db_session
            close_session = False
        else:
            db = next(get_db())
            close_session = True

        try:
            async for result in self.execute(params, db):
                yield result
        finally:
            # Only close if we created the session
            if close_session:
                db.close()

    async def execute(
        self, params: Dict[str, Any], db: Session
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            if not self._current_user:
                yield {"type": "error", "data": {"message": "Current user not found"}}
                return

            case_id = params.get("case_id")
            if not case_id:
                yield {"type": "error", "data": {"message": "Case ID is required"}}
                return

            # Verify user has access to this case
            stmt = select(CaseUserLink).where(
                CaseUserLink.case_id == case_id,
                CaseUserLink.user_id == self._current_user.id,
            )
            result = db.execute(stmt)
            if not result.first():
                yield {
                    "type": "error",
                    "data": {"message": "You do not have access to this case"},
                }
                return

            # Get all entities from the specified case
            case_entities = await self._get_case_entities(db, case_id)

            for entity in case_entities:
                # Extract and normalize entity name based on type
                entity_name = self._get_display_name(entity.data, entity.entity_type)
                employer_name = None

                if entity.entity_type == "person" and entity.data:
                    employer_name = entity.data.get("employer", "")

                if not entity_name:
                    continue

                # Find name matches
                name_matches = await self._find_name_matches(db, entity, entity_name)

                if name_matches:
                    match_data = {
                        "entity_id": entity.id,
                        "entity_name": entity_name,
                        "entity_type": entity.entity_type,
                        "match_type": "name",
                        "case_id": case_id,
                        "matches": name_matches,
                    }
                    yield {"type": "data", "data": match_data}

                # If this is a person entity with an employer, check for employer matches
                if employer_name:
                    employer_matches = await self._find_employer_matches(
                        db, entity, employer_name
                    )

                    if employer_matches:
                        match_data = {
                            "entity_id": entity.id,
                            "entity_name": entity_name,
                            "entity_type": entity.entity_type,
                            "match_type": "employer",
                            "employer_name": employer_name,
                            "case_id": case_id,
                            "matches": employer_matches,
                        }
                        yield {"type": "data", "data": match_data}

        except Exception as e:
            yield {
                "type": "error",
                "data": {"message": f"Error during correlation scan: {str(e)}"},
            }

    async def _get_case_entities(self, db: Session, case_id: int) -> List[Entity]:
        """Get all entities for a specific case"""
        stmt = select(Entity).where(Entity.case_id == case_id)
        result = db.execute(stmt)
        return result.scalars().all()

    async def _find_name_matches(
        self, db: Session, source_entity: Entity, entity_name: str
    ) -> List[Dict[str, Any]]:
        """Find entities with matching names across all cases assigned to the current user"""
        # Get all accessible entities of the same type
        stmt = (
            select(Entity, Case)
            .join(Case)
            .join(CaseUserLink, Case.id == CaseUserLink.case_id)
            .where(
                Entity.id != source_entity.id,
                Entity.entity_type == source_entity.entity_type,
                CaseUserLink.user_id == self._current_user.id,
            )
        )
        result = db.execute(stmt)

        matches = []
        normalized_source_name = entity_name.lower()

        for entity, case in result:
            # Check if names match based on entity type
            match_name = self._get_display_name(entity.data, entity.entity_type)
            if match_name and match_name.lower() == normalized_source_name:
                matches.append(
                    {
                        "entity_id": entity.id,
                        "entity_type": entity.entity_type,
                        "case_id": entity.case_id,
                        "case_number": case.case_number,
                        "case_title": case.title,
                    }
                )

        return matches

    async def _find_employer_matches(
        self, db: Session, source_entity: Entity, employer_name: str
    ) -> List[Dict[str, Any]]:
        """Find entities with matching employer names across all cases assigned to the current user"""
        stmt = (
            select(Entity, Case)
            .join(Case)
            .join(CaseUserLink, Case.id == CaseUserLink.case_id)
            .where(
                Entity.id != source_entity.id,
                Entity.entity_type == "person",
                CaseUserLink.user_id == self._current_user.id,
            )
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
                    {
                        "entity_id": entity.id,
                        "entity_type": entity.entity_type,
                        "case_id": entity.case_id,
                        "case_number": case.case_number,
                        "case_title": case.title,
                        "person_name": person_name,
                    }
                )

        return matches

    def _get_primary_fields_for_entity(self, entity_type: str) -> List[str]:
        """Dynamically determine primary identifier fields for an entity type"""
        if entity_type not in ENTITY_TYPE_SCHEMAS:
            return []

        schema_class = ENTITY_TYPE_SCHEMAS[entity_type]
        annotations = getattr(schema_class, '__annotations__', {})
        
        # Look for required fields (non-Optional)
        required_fields = []
        name_like_fields = []
        
        for field_name, field_type in annotations.items():
            # Skip complex types, focus on simple identifiers
            if get_origin(field_type) is not None:
                # This is a generic type like Optional[str], List[str], etc.
                if get_origin(field_type) is type(Optional[str]):  # Union type (Optional)
                    continue
            
            # Check if it's a simple string type (likely identifier)
            if field_type == str:
                required_fields.append(field_name)
            
            # Collect name-like fields for fallback
            if any(keyword in field_name.lower() for keyword in ['name', 'domain', 'ip', 'address']):
                name_like_fields.append(field_name)

        # Special handling for person entities (combine first_name + last_name)
        if entity_type == "person":
            if "first_name" in annotations and "last_name" in annotations:
                return ["first_name", "last_name"]
        
        # Use required fields if available
        if required_fields:
            return required_fields
        
        # Fallback to name-like fields
        if name_like_fields:
            return name_like_fields[:1]  # Take first name-like field
        
        # Final fallback: look for common identifier patterns
        common_patterns = [entity_type, "name", "title", "identifier"]
        for pattern in common_patterns:
            if pattern in annotations:
                return [pattern]
        
        return []

    def _get_display_name(self, data: dict, entity_type: str) -> str:
        """Extract display name from entity data based on type"""
        if not data:
            return ""

        # Check if entity type is supported in schemas
        if entity_type not in ENTITY_TYPE_SCHEMAS:
            # Fallback for unknown entity types
            return data.get("Name", "")

        # Dynamically get primary fields for this entity type
        primary_fields = self._get_primary_fields_for_entity(entity_type)
        
        if not primary_fields:
            # Fallback: try to use a field that matches the entity type name
            return data.get(entity_type, data.get("name", ""))

        # Extract values for primary fields
        field_values = []
        for field in primary_fields:
            value = data.get(field, "")
            if value:
                field_values.append(str(value))

        # Combine multiple fields with space (e.g., first_name + last_name)
        return " ".join(field_values).strip()

    def _format_evidence_content(
        self, results: List[Dict[str, Any]], params: Dict[str, Any]
    ) -> str:
        """Custom formatting for correlation scan evidence"""
        if not results:
            return ""

        # Format the evidence content
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

            # Create correlation context based on match type
            if match_type == "name":
                correlation_context = (
                    f"Found an entity named '{entity_name}' that appears in multiple cases. "
                    f"This may indicate the same {entity_type} is involved in different investigations."
                )
            elif match_type == "employer":
                correlation_context = (
                    f"Found multiple people who work at '{match_group.get('employer_name', '')}'. "
                    f"This employer connection may indicate a relationship between these cases."
                )

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

            content_lines.extend(
                [
                    "-" * 30,
                    "",
                    "Related Cases and Details:",
                    "",
                ]
            )

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
                else:
                    match_info.append(f"Relationship: Same {entity_type} name match")

                match_info.append("")
                content_lines.extend(match_info)

            content_lines.append("=" * 50 + "\n")

        return "\n".join(content_lines)
