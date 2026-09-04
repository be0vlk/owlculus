"""Opt-in subprocess support for command-line plugins."""

import asyncio
import subprocess
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Sequence
from concurrent.futures import ThreadPoolExecutor

from .plugin_types import Payload


class SubprocessPluginMixin(ABC):
    @abstractmethod
    def parse_output(self, line: str) -> Payload | None: ...

    async def run_subprocess(
        self, command: Sequence[str]
    ) -> AsyncGenerator[Payload, None]:
        executor = ThreadPoolExecutor(max_workers=3)
        try:
            loop = asyncio.get_running_loop()
            process = await loop.run_in_executor(
                executor,
                lambda: subprocess.Popen(
                    list(command),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                ),
            )
            assert process.stdout is not None
            while line := await loop.run_in_executor(executor, process.stdout.readline):
                parsed = self.parse_output(line.strip())
                if parsed is not None:
                    yield parsed
            if await loop.run_in_executor(executor, process.wait):
                assert process.stderr is not None
                yield {
                    "error": await loop.run_in_executor(executor, process.stderr.read)
                }
        finally:
            executor.shutdown(wait=False)
