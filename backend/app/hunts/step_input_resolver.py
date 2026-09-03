"""Pure resolution of hunt step input expressions."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class InputExpressionError(ValueError):
    """Raised when a hunt input expression is not valid."""


@dataclass(frozen=True)
class AbsentInput:
    """Explicit result for a well-formed path that is not present."""

    def __repr__(self) -> str:
        return "ABSENT"


ABSENT = AbsentInput()

_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_EXPRESSION = re.compile(
    rf"^(?P<root>{_IDENTIFIER})(?P<path>(?:\.{_IDENTIFIER}(?:\[\d+\])*)+)$"
)
_PATH_TOKEN = re.compile(rf"\.({_IDENTIFIER})|\[(\d+)\]")


def parse_input_expression(expression: str) -> tuple[str, tuple[str | int, ...]]:
    """Parse an expression into its source name and traversal path."""
    match = _EXPRESSION.fullmatch(expression)
    if match is None or not match.group("path"):
        raise InputExpressionError(f"Invalid hunt input expression {expression!r}")

    path: list[str | int] = []
    for token in _PATH_TOKEN.finditer(match.group("path")):
        key, index = token.groups()
        path.append(key if key is not None else int(index))
    return match.group("root"), tuple(path)


def resolve_step_input(
    expression: str,
    initial_parameters: Mapping[str, Any],
    step_outputs: Mapping[str, Any],
) -> Any | AbsentInput:
    """Resolve one mapping expression without mutating hunt state."""
    source, path = parse_input_expression(expression)
    current: Any
    if source == "initial":
        current = initial_parameters
    elif source in step_outputs:
        current = step_outputs[source]
    else:
        return ABSENT

    for part in path:
        if isinstance(part, str) and isinstance(current, Mapping):
            if part not in current:
                return ABSENT
            current = current[part]
        elif (
            isinstance(part, int)
            and isinstance(current, Sequence)
            and not isinstance(current, (str, bytes, bytearray))
        ):
            if part >= len(current):
                return ABSENT
            current = current[part]
        else:
            return ABSENT
    return current
