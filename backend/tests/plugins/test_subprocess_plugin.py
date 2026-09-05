"""Public subprocess adapter streaming and cleanup behavior."""

import asyncio
import os
import sys

import pytest

from app.plugins.subprocess_plugin import SubprocessPluginMixin


class Lines(SubprocessPluginMixin):
    def parse_output(self, line):
        return {"line": line}


@pytest.mark.asyncio
async def test_stderr_cannot_block_stdout_streaming():
    async def collect():
        return [
            item
            async for item in Lines().run_subprocess(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stderr.write('x' * 131072); print('done'); sys.exit(1)",
                ]
            )
        ]

    results = await asyncio.wait_for(collect(), timeout=3)
    assert results[0] == {"line": "done"}
    assert results[1] == {"error": "x" * 65536}


@pytest.mark.asyncio
async def test_closing_stream_reaps_its_process():
    stream = Lines().run_subprocess(
        [
            sys.executable,
            "-c",
            "import os,time; print(os.getpid(), flush=True); time.sleep(600)",
        ]
    )
    first = await asyncio.wait_for(anext(stream), timeout=3)
    pid = int(first["line"])
    await asyncio.wait_for(stream.aclose(), timeout=3)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
