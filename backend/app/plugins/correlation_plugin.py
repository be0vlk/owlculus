"""
Plugin for scanning and correlating entity names across cases
"""

from typing import AsyncGenerator, Dict, Any, Optional, List
from sqlmodel import select, Session

from .base_plugin import BasePlugin
from ..database.models import Entity, Case, CaseUserLink
from ..core.dependencies import get_db
from ..core.utils import get_utc_now


class CorrelationScan(BasePlugin):
    """Plugin for finding matching entities across cases"""

    def __init__(self):
        super().__init__(display_name="Correlation Scan")
        self.description = "Scans for matching entities across your cases"
        self.category = "Other"
        self.save_to_case = True
        self.parameters = {
            "case_id": {
                "type": "integer",
                "description": "ID of the case to scan",
                "required": True,
            }
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

        db = next(get_db())
        try:
            async for result in self.execute(params, db):
                yield result
        finally:
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

            # Collect all matches
            all_matches = []

            for entity in case_entities:
                # Extract and normalize entity name based on type
                entity_name = self._get_display_name(entity.data, entity.entity_type)
                employer_name = None
                
                if entity.entity_type == "person" and entity.data:
                    employer_name = entity.data.get("employer", "")
                
                if not entity_name:
                    continue

                # Find name matches
                name_matches = await self._find_name_matches(
                    db, entity, entity_name
                )

                if name_matches:
                    match_data = {
                        "entity_id": entity.id,
                        "entity_name": entity_name,
                        "entity_type": entity.entity_type,
                        "match_type": "name",
                        "case_id": case_id,
                        "matches": name_matches,
                    }
                    all_matches.append(match_data)
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
                        all_matches.append(match_data)
                        yield {"type": "data", "data": match_data}

            # Create evidence if matches were found
            if all_matches:
                await self._create_evidence_for_matches(db, case_id, all_matches)
                
            # Send completion signal
            yield {"type": "complete", "data": {"message": "Correlation scan completed"}}
            
        except Exception as e:
            yield {"type": "error", "data": {"message": f"Error during correlation scan: {str(e)}"}}

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
                matches.append({
                    "entity_id": entity.id,
                    "entity_type": entity.entity_type,
                    "case_id": entity.case_id,
                    "case_number": case.case_number,
                    "case_title": case.title,
                })

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
            if entity.data and entity.data.get("employer", "").lower() == normalized_employer:
                person_name = self._get_display_name(entity.data, "person")
                matches.append({
                    "entity_id": entity.id,
                    "entity_type": entity.entity_type,
                    "case_id": entity.case_id,
                    "case_number": case.case_number,
                    "case_title": case.title,
                    "person_name": person_name,
                })

        return matches

    def _get_display_name(self, data: dict, entity_type: str) -> str:
        """Extract display name from entity data based on type"""
        if not data:
            return ""
            
        if entity_type == "company":
            return data.get("name", "")
        elif entity_type == "person":
            first_name = data.get("first_name", "")
            last_name = data.get("last_name", "")
            return f"{first_name} {last_name}".strip()
        else:
            return data.get("Name", "")

    async def _create_evidence_for_matches(
        self,
        db: Session,
        case_id: int,
        matches: List[Dict[str, Any]],
    ) -> None:
        """Create single evidence entry for all entity matches"""
        if not matches:
            return

        # Format the evidence content
        content_lines = [
            "Correlation Scan Results",
            "=" * 50,
            "",
            f"Total entities with matches: {len(matches)}",
            "",
        ]

        for match_group in matches:
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

        content = "\n".join(content_lines)

        # Use base plugin's evidence saving system
        await self._save_evidence_to_case(
            db=db,
            case_id=case_id,
            content=content,
            filename=f"correlation_scan_results_{get_utc_now().strftime('%Y%m%d_%H%M%S')}.txt",
        )