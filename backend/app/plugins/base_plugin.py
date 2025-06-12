"""
Base plugin class that all OSINT tools must inherit from
"""

import asyncio
import ipaddress
import json
import shlex
import subprocess
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from tempfile import SpooledTemporaryFile
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from app.core.dependencies import get_db
from app.core.utils import get_utc_now
from app.database import models
from app.schemas import evidence_schema as schemas
from app.schemas.entity_schema import EntityCreate, IpAddressData
from app.schemas.evidence_schema import EvidenceCreate
from app.services.entity_service import EntityService
from app.services.evidence_service import EvidenceService
from app.services.system_config_service import SystemConfigService
from fastapi import UploadFile
from sqlalchemy.orm import Session


class BasePlugin(ABC):
    """Base class for all plugins to inherit from"""

    def __init__(
        self, display_name: Optional[str] = None, db_session: Optional[Session] = None
    ):
        self.name: str = self.__class__.__name__
        self.display_name: str = display_name or self.name
        self.description: str = ""
        self.enabled: bool = True
        self.category: str = "Other"  # Default category, change for each plugin
        self.evidence_category: str = "Other"  # Category for evidence storage
        self.parameters: Dict[str, Dict[str, Any]] = {}
        self.save_to_case: bool = False  # Whether to save plugin output as evidence
        self.api_key_requirements: List[str] = []  # List of required API key providers
        self._executor = ThreadPoolExecutor(
            max_workers=3, thread_name_prefix=f"{self.name}_executor"
        )
        self._current_user: Optional[models.User] = None
        self._evidence_results: List[Dict[str, Any]] = (
            []
        )  # Collect results for evidence saving
        self._current_params: Optional[Dict[str, Any]] = None
        self._db_session: Optional[Session] = db_session  # Injected database session

        # Validate evidence_category on initialization
        self._validate_evidence_category()

    def _validate_evidence_category(self) -> None:
        """Validate that evidence_category is a valid evidence category"""
        if self.evidence_category not in EvidenceCreate.VALID_CATEGORIES:
            raise ValueError(
                f"Invalid evidence_category '{self.evidence_category}' for plugin {self.name}. "
                f"Must be one of: {', '.join(EvidenceCreate.VALID_CATEGORIES)}"
            )

    async def _read_stream(self, stream) -> AsyncGenerator[str, None]:
        """Read from a stream asynchronously"""
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(self._executor, stream.readline)
            if not line:
                break
            yield line.strip()

    async def _run_subprocess(
        self,
        command: Union[str, List[str]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a subprocess command asynchronously

        Args:
            command: Command to execute

        Yields:
            Structured output data
        """

        sanitized_command = [shlex.quote(arg) for arg in command]

        loop = asyncio.get_event_loop()
        process = await loop.run_in_executor(
            self._executor,
            lambda: subprocess.Popen(
                sanitized_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            ),
        )

        # Stream output asynchronously
        async for line in self._read_stream(process.stdout):
            try:
                parsed_data = self.parse_output(line)
                if parsed_data is not None:  # Skip None results
                    yield parsed_data
            except Exception as e:
                yield {"error": str(e)}

        # Wait for process to complete asynchronously
        returncode = await loop.run_in_executor(self._executor, process.wait)

        if returncode != 0:
            # Read error asynchronously if process failed
            error = await loop.run_in_executor(self._executor, process.stderr.read)
            yield {"error": error}

    @abstractmethod
    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a line of output into structured data

        Args:
            line: Raw output line from command

        Returns:
            Dictionary containing parsed data, or None to skip this line
        """
        pass

    @abstractmethod
    async def run(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the plugin with the given parameters

        Args:
            params: Optional dictionary of parameters for the plugin

        Yields:
            Structured output data
        """
        pass

    async def _save_evidence_to_case(
        self,
        db: Session,
        case_id: int,
        content: str,
        filename: Optional[str] = None,
        save_to_case: bool = False,
    ) -> None:
        """
        Save plugin output as evidence to the specified case

        Args:
            db: Database session
            case_id: ID of the case to save evidence to
            content: Content to save as evidence
            filename: Optional custom filename, defaults to plugin name with timestamp
            save_to_case: Whether to save the evidence (defaults to False)
        """
        if not save_to_case or not content:
            return

        # Create a temporary file with the content
        temp_file = SpooledTemporaryFile()
        temp_file.write(content.encode("utf-8"))
        temp_file.seek(0)

        # Create an UploadFile with the temp file
        timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
        file = UploadFile(
            filename=filename or f"{self.name}_output_{timestamp}.txt",
            file=temp_file,
            headers={"content-type": "text/plain"},
        )

        # Create evidence schema
        evidence_create = schemas.EvidenceCreate(
            case_id=case_id,
            title=f"{self.display_name} results.txt",
            description=f"Output generated by {self.display_name} plugin",
            source=self.name,
            type="plugin_output",
            category=self.evidence_category,
        )

        # Save evidence using evidence service
        evidence_service = EvidenceService(db)
        await evidence_service.create_evidence(
            evidence=evidence_create,
            current_user=self._current_user,
            file=file,
        )

        temp_file.close()

    def _get_enhanced_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get parameters with automatic save_to_case injection"""
        enhanced_params = self.parameters.copy()

        # Always add save_to_case parameter if not already defined
        if "save_to_case" not in enhanced_params:
            enhanced_params["save_to_case"] = {
                "type": "boolean",
                "description": f"Save {self.display_name} results as evidence to the case",
                "default": False,
                "required": False,
            }

        return enhanced_params

    def add_evidence_result(self, result: Dict[str, Any]) -> None:
        """Add a result to be included in evidence saving"""
        self._evidence_results.append(result)

    async def save_collected_evidence(self) -> None:
        """Save all collected evidence results to the case"""
        if not self._current_params or not self._evidence_results:
            return

        save_to_case = self._current_params.get("save_to_case", False)
        case_id = self._current_params.get("case_id")

        if not save_to_case or not case_id:
            return

        # Use injected session if available, otherwise get a new one
        if self._db_session:
            db = self._db_session
            close_session = False
        else:
            db = next(get_db())
            close_session = True

        try:
            # Format the evidence content
            content = self._format_evidence_content(
                self._evidence_results, self._current_params
            )

            if content:
                timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
                await self._save_evidence_to_case(
                    db=db,
                    case_id=case_id,
                    content=content,
                    filename=f"{self.name}_results_{timestamp}.txt",
                    save_to_case=True,
                )

            # Auto-create IP entities if plugin supports it
            await self._create_ip_entities_from_results()
        finally:
            # Only close if we created the session
            if close_session:
                db.close()

    def _format_evidence_content(
        self, results: List[Dict[str, Any]], params: Dict[str, Any]
    ) -> str:
        """Format evidence content - can be overridden by plugins for custom formatting"""
        content_lines = [
            f"{self.display_name} Results",
            "=" * 50,
            "",
            f"Total results: {len(results)}",
            f"Execution time: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "Parameters:",
            "-" * 20,
        ]

        # Add parameters (excluding sensitive ones)
        for key, value in params.items():
            if key not in ["save_to_case", "case_id"]:
                content_lines.append(f"{key}: {value}")

        content_lines.extend(
            [
                "",
                "Results:",
                "-" * 20,
                "",
            ]
        )

        # Add results in JSON format for readability
        for i, result in enumerate(results, 1):
            content_lines.extend(
                [
                    f"Result #{i}:",
                    json.dumps(result, indent=2, default=str),
                    "",
                ]
            )

        return "\n".join(content_lines)

    async def execute_with_evidence_collection(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute plugin with automatic evidence collection"""
        self._current_params = params or {}
        self._evidence_results = []  # Reset evidence collection

        try:
            async for result in self.run(params):
                # Collect data results for evidence saving
                if result.get("type") == "data":
                    self.add_evidence_result(result.get("data", {}))

                yield result
        finally:
            # Save evidence at the end of execution
            await self.save_collected_evidence()

    def check_api_key_requirements(self, db: Session) -> Dict[str, bool]:
        """Check if required API keys are configured."""
        if not self.api_key_requirements:
            return {}

        config_service = SystemConfigService(db)
        api_key_status = {}

        for provider in self.api_key_requirements:
            api_key_status[provider] = config_service.is_provider_configured(provider)

        return api_key_status

    def get_missing_api_keys(self, db: Session) -> List[str]:
        """Get list of missing API keys required by this plugin."""
        if not self.api_key_requirements:
            return []

        api_key_status = self.check_api_key_requirements(db)
        return [
            provider
            for provider, is_configured in api_key_status.items()
            if not is_configured
        ]

    def _is_ip_address(self, value: str) -> bool:
        """Check if the given value is a valid IP address"""
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    async def _create_ip_entities_from_results(self) -> None:
        """Extract IP addresses from results and create or enrich entities (to be overridden by plugins)"""
        case_id = self._current_params.get("case_id")
        if not case_id:
            return

        # Extract unique IP addresses from results
        discovered_ips = self._extract_unique_ips_from_results()

        if not discovered_ips:
            return

        # Use injected session if available, otherwise get a new one
        if self._db_session:
            db = self._db_session
            close_session = False
        else:
            db = next(get_db())
            close_session = True

        try:
            entity_service = EntityService(db)
            created_count = 0
            enriched_count = 0
            failed_count = 0

            for ip_data in discovered_ips:
                try:
                    ip_address = ip_data["ip"]
                    description = ip_data["description"]

                    # Check if IP entity already exists
                    existing_entity = await entity_service.find_entity_by_ip_address(
                        case_id, ip_address, current_user=self._current_user
                    )

                    if existing_entity:
                        # Enrich existing entity with new data
                        await entity_service.enrich_entity_description(
                            existing_entity.id,
                            description,
                            current_user=self._current_user,
                        )
                        enriched_count += 1
                    else:
                        # Create new IP address entity
                        entity_create = EntityCreate(
                            entity_type="ip_address",
                            data=IpAddressData(
                                ip_address=ip_address, description=description
                            ).model_dump(),
                        )

                        await entity_service.create_entity(
                            case_id=case_id,
                            entity=entity_create,
                            current_user=self._current_user,
                        )
                        created_count += 1

                except Exception:
                    # Log error but continue with other IPs
                    failed_count += 1
                    continue

            # Entity operations completed silently

        except Exception:
            # Don't break evidence saving if entity creation fails completely
            pass
        finally:
            # Only close if we created the session
            if close_session:
                db.close()

    def _extract_unique_ips_from_results(self) -> list[dict]:
        """Extract unique IP addresses with metadata from collected results (to be overridden by plugins)"""
        # Default implementation - plugins should override this method
        # to extract IPs specific to their result format
        return []

    def _generate_ip_description(self, ip_address: str, context: str = "") -> str:
        """Generate a descriptive string for the IP address entity (can be overridden by plugins)"""
        plugin_name = self.display_name
        context_part = f" for '{context}'" if context else ""
        return f"Discovered via {plugin_name} lookup{context_part}"

    def get_metadata(self) -> Dict[str, Any]:
        """Return plugin metadata with enhanced parameters"""
        metadata = {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "enabled": self.enabled,
            "category": self.category,
            "parameters": self._get_enhanced_parameters(),
            "api_key_requirements": self.api_key_requirements,
        }

        # Include API key status if we have a database session
        if self._db_session:
            metadata["api_key_status"] = self.check_api_key_requirements(
                self._db_session
            )

        return metadata

    def __del__(self):
        """Cleanup thread pool on plugin deletion"""
        self._executor.shutdown(wait=False)
