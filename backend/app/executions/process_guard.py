"""Database-free watchdog for the provider group, including supervisor SIGKILL."""

import os
import select
import signal
import subprocess
import sys
import time

from app.executions.limits import CLEANUP_SECONDS


def main():
    # The supervisor creates this session before any provider process exists. All
    # descendants inherit its group. Only the supervisor owns the pipe writer.
    deadline = float(sys.argv[1])
    process = subprocess.Popen(sys.argv[2:], stdin=subprocess.DEVNULL)
    pending = b""
    while process.poll() is None:
        readable, _, _ = select.select([sys.stdin], [], [], 0.1)
        if readable:
            chunk = os.read(sys.stdin.fileno(), 4096)
            if not chunk:
                break
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                deadline = float(line)
        if time.monotonic() >= deadline - CLEANUP_SECONDS:
            break
    else:
        # A finished provider may have left descendants behind. Clean the group
        # even when the supervisor died before it could observe that exit.
        os.killpg(os.getpgrp(), signal.SIGKILL)
    # On pipe EOF or lease expiry the supervisor cannot be trusted to clean up.
    # Ignore our own TERM, allowing cooperative providers a bounded exit window.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.killpg(os.getpgrp(), signal.SIGTERM)
    time.sleep(CLEANUP_SECONDS - 1)
    os.killpg(os.getpgrp(), signal.SIGKILL)


if __name__ == "__main__":
    main()
