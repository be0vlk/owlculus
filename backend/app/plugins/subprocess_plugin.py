"""Opt-in streaming subprocess support with cancellation-owned cleanup."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Sequence

from .plugin_types import Payload


class SubprocessPluginMixin(ABC):
    @abstractmethod
    def parse_output(self, line: str) -> Payload | None: ...

    async def run_subprocess(
        self, command: Sequence[str]
    ) -> AsyncGenerator[Payload, None]:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        errors = bytearray()

        async def drain_errors():
            assert process.stderr is not None
            while chunk := await process.stderr.read(8192):
                errors.extend(chunk[: max(0, 65536 - len(errors))])

        drain = asyncio.create_task(drain_errors())
        try:
            assert process.stdout is not None
            while line := await process.stdout.readline():
                parsed = self.parse_output(line.decode(errors="replace").strip())
                if parsed is not None:
                    yield parsed
            code = await process.wait()
            await drain
            if code:
                yield {"error": errors.decode(errors="replace")}
        finally:
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), timeout=1)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            drain.cancel()
            await asyncio.gather(drain, return_exceptions=True)
