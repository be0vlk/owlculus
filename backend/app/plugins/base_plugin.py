"""
Base plugin class that all OSINT tools must inherit from
"""

from abc import ABC, abstractmethod
import asyncio
import subprocess
import shlex
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Dict, Any, Optional, List, Union
from app.schemas import evidence_schema as schemas
from app.database import models
from app.core.utils import get_utc_now
from tempfile import SpooledTemporaryFile
from fastapi import UploadFile
from app.services.evidence_service import EvidenceService
from sqlalchemy.orm import Session


class BasePlugin(ABC):
    """Base class for all plugins to inherit from"""

    def __init__(self, display_name: Optional[str] = None):
        self.name: str = self.__class__.__name__
        self.display_name: str = display_name or self.name
        self.description: str = ""
        self.enabled: bool = True
        self.category: str = "Other"  # Default category, change for each plugin
        self.parameters: Dict[str, Dict[str, Any]] = {}
        self.save_to_case: bool = False  # Whether to save plugin output as evidence
        self._executor = ThreadPoolExecutor(
            max_workers=3, thread_name_prefix=f"{self.name}_executor"
        )
        self._current_user: Optional[models.User] = None

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
    ) -> None:
        """
        Save plugin output as evidence to the specified case

        Args:
            db: Database session
            case_id: ID of the case to save evidence to
            content: Content to save as evidence
            filename: Optional custom filename, defaults to plugin name with timestamp
        """
        if not self.save_to_case or not content:
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
            category=self.category,
        )

        # Save evidence using evidence service
        evidence_service = EvidenceService(db)
        await evidence_service.create_evidence(
            evidence=evidence_create,
            current_user=self._current_user,
            file=file,
        )

        temp_file.close()

    def get_metadata(self) -> Dict[str, Any]:
        """Return plugin metadata"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "enabled": self.enabled,
            "category": self.category,
            "parameters": self.parameters,
        }

    def __del__(self):
        """Cleanup thread pool on plugin deletion"""
        self._executor.shutdown(wait=False)
