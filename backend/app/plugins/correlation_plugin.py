"""
Plugin for scanning and correlating entity names across cases
"""

from typing import AsyncGenerator, Dict, Any, Optional
import json
from sqlalchemy import select
from sqlalchemy.orm import Session

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
            yield json.loads(
                json.dumps(
                    {"type": "error", "data": {"message": "Parameters are required"}}
                )
            )
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
        if not self._current_user:
            yield json.loads(
                json.dumps(
                    {"type": "error", "data": {"message": "Current user not found"}}
                )
            )
            return

        case_id = params.get("case_id")
        if not case_id:
            yield json.loads(
                json.dumps(
                    {"type": "error", "data": {"message": "Case ID is required"}}
                )
            )
            return

        # Verify user has access to this case
        stmt = select(CaseUserLink).where(
            CaseUserLink.case_id == case_id,
            CaseUserLink.user_id == self._current_user.id,
        )
        result = db.execute(stmt)
        if not result.first():
            yield json.loads(
                json.dumps(
                    {
                        "type": "error",
                        "data": {"message": "You do not have access to this case"},
                    }
                )
            )
            return

        # Get all entities from the specified case
        case_entities = await self._get_case_entities(db, case_id)

        # Collect all matches
        all_matches = []

        for entity in case_entities:
            entity_name = None
            employer_name = None

            # Handle different entity types
            if entity.entity_type == "company":
                entity_name = entity.data.get("name", "")
            elif entity.entity_type == "person":
                first_name = entity.data.get("first_name", "")
                last_name = entity.data.get("last_name", "")
                employer_name = entity.data.get("employer", "")
                if first_name or last_name:
                    entity_name = f"{first_name} {last_name}".strip()
            else:
                entity_name = entity.data.get("Name", "")  # fallback for other types

            if not entity_name:
                continue

            # Store original case for display
            original_name = entity_name
            entity_name = entity_name.lower()

            # Find name matches in all cases
            matches = await self._find_name_matches(
                db, entity_name, entity.id, entity.entity_type
            )

            if matches:
                all_matches.append(
                    {
                        "entity_id": entity.id,
                        "entity_name": original_name,
                        "entity_type": entity.entity_type,
                        "match_type": "name",
                        "matches": matches,
                    }
                )

                yield json.loads(
                    json.dumps(
                        {
                            "type": "data",
                            "data": {
                                "entity_id": entity.id,
                                "entity_name": original_name,
                                "entity_type": entity.entity_type,
                                "match_type": "name",
                                "case_id": case_id,
                                "matches": matches,
                            },
                        }
                    )
                )

            # If this is a person entity with an employer, check for employer matches
            if entity.entity_type == "person" and employer_name:
                employer_matches = await self._find_employer_matches(
                    db, employer_name, entity.id
                )

                if employer_matches:
                    all_matches.append(
                        {
                            "entity_id": entity.id,
                            "entity_name": original_name,
                            "entity_type": entity.entity_type,
                            "match_type": "employer",
                            "employer_name": employer_name,
                            "matches": employer_matches,
                        }
                    )

                    yield json.loads(
                        json.dumps(
                            {
                                "type": "data",
                                "data": {
                                    "entity_id": entity.id,
                                    "entity_name": original_name,
                                    "entity_type": entity.entity_type,
                                    "match_type": "employer",
                                    "employer_name": employer_name,
                                    "case_id": case_id,
                                    "matches": employer_matches,
                                },
                            }
                        )
                    )

        # Create a single evidence file for all matches
        if all_matches:
            await self._create_evidence_for_matches(db, case_id, all_matches)

    async def _get_case_entities(self, db: Session, case_id: int) -> list[Entity]:
        """Get all entities for a specific case"""
        stmt = select(Entity).where(Entity.case_id == case_id)
        result = db.execute(stmt)
        return result.scalars().all()

    async def _find_name_matches(
        self, db: Session, name: str, exclude_entity_id: int, entity_type: str
    ) -> list[Dict[str, Any]]:
        """Find entities with matching names across all cases assigned to the current user"""
        stmt = (
            select(Entity, Case)
            .join(Case)
            .join(CaseUserLink, Case.id == CaseUserLink.case_id)
            .where(
                Entity.id != exclude_entity_id,
                Entity.entity_type == entity_type,
                CaseUserLink.user_id == self._current_user.id,
            )
        )
        result = db.execute(stmt)

        matches = []
        for entity, case in result:
            match_found = False

            if entity_type == "company":
                match_found = entity.data.get("name", "").lower() == name
            elif entity_type == "person":
                first_name = entity.data.get("first_name", "").lower()
                last_name = entity.data.get("last_name", "").lower()
                full_name = f"{first_name} {last_name}".strip()
                match_found = full_name == name
            else:
                match_found = entity.data.get("Name", "").lower() == name

            if match_found:
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
        self, db: Session, employer_name: str, exclude_entity_id: int
    ) -> list[Dict[str, Any]]:
        """Find entities with matching employer names across all cases assigned to the current user

        Args:
            db: Database session
            employer_name: Name of the employer to match
            exclude_entity_id: Entity ID to exclude from matches

        Returns:
            List of matching entities with their case information
        """
        stmt = (
            select(Entity, Case)
            .join(Case)
            .join(CaseUserLink, Case.id == CaseUserLink.case_id)
            .where(
                Entity.id != exclude_entity_id,
                Entity.entity_type == "person",
                CaseUserLink.user_id == self._current_user.id,
            )
        )
        result = db.execute(stmt)

        matches = []
        for entity, case in result:
            if entity.data is None:
                continue
            employer_value = entity.data.get("employer")
            if employer_value is None:
                continue
            employer = employer_value.lower()
            if employer and employer == employer_name.lower():
                matches.append(
                    {
                        "entity_id": entity.id,
                        "entity_type": entity.entity_type,
                        "case_id": entity.case_id,
                        "case_number": case.case_number,
                        "case_title": case.title,
                        "person_name": f"{entity.data.get('first_name', '')} {entity.data.get('last_name', '')}".strip(),
                    }
                )

        return matches

    async def _create_evidence_for_matches(
        self,
        db: Session,
        case_id: int,
        matches: list[Dict[str, Any]],
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
