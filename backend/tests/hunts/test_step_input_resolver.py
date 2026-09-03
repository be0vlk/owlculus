"""Behavioural tests for hunt step input expressions."""

import re

import pytest

from app.hunts.step_input_resolver import (
    ABSENT,
    InputExpressionError,
    resolve_step_input,
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("initial.domain", "example.com"),
        ("dns_records.result_count", 1),
        ("dns_records.results[0]", {"results": [{"records": ["192.0.2.1"]}]}),
        ("dns_records.results[0].results[0].records[0]", "192.0.2.1"),
        ("nested.matrix[0][1].value", "found"),
    ],
)
def test_resolves_documented_input_expression_forms(expression, expected):
    initial = {"domain": "example.com"}
    step_outputs = {
        "dns_records": {
            "result_count": 1,
            "results": [{"results": [{"records": ["192.0.2.1"]}]}],
        },
        "nested": {"matrix": [[{}, {"value": "found"}]]},
    }

    assert resolve_step_input(expression, initial, step_outputs) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "initial.missing",
        "dns_records.results[4]",
        "unknown.value",
        "dns_records.results[0].missing",
    ],
)
def test_missing_input_path_has_an_explicit_absent_value(expression):
    assert (
        resolve_step_input(expression, {}, {"dns_records": {"results": []}}) is ABSENT
    )


@pytest.mark.parametrize(
    "expression",
    ["", "initial", ".domain", "initial..domain", "results[]", "results[-1]"],
)
def test_malformed_input_expression_names_the_expression(expression):
    with pytest.raises(InputExpressionError, match=re.escape(repr(expression))):
        resolve_step_input(expression, {}, {})
