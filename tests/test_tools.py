import pytest

from app.schemas import ToolCall
from app.tools import calculate, run_tool


@pytest.mark.parametrize(
    "expression,expected",
    [("12000*1.18", 14160), ("(12000*3)*18/100", 6480), ("-2+5", 3), ("2**3", 8), ("7//2", 3), ("7%2", 1)],
)
def test_arithmetic(expression, expected):
    assert calculate(expression) == pytest.approx(expected)


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('id')",
        "open('secret')",
        "a+1",
        "True+1",
        "[1][0]",
        "2**100000",
        "1/0",
        "1e309",
        "(-1)**0.5",
        "9" * 201,
    ],
)
def test_unsafe_or_invalid_calculations(expression):
    with pytest.raises((ValueError, ArithmeticError)):
        calculate(expression)


def test_tool_errors_are_data():
    result = run_tool(ToolCall(name="calculator", arguments={"expression": "1/0"}, reason="test"))
    assert not result["ok"] and "zero" in result["error"]


@pytest.mark.parametrize(
    "name,args",
    [
        ("date_difference", {"start": "invalid", "end": "2026-09-25"}),
        ("current_time", {"timezone": "No/SuchZone"}),
        ("calculator", {"expression": "1+1", "code": "bad"}),
    ],
)
def test_tool_argument_errors(name, args):
    assert not run_tool(ToolCall(name=name, arguments=args, reason="test"))["ok"]


def test_calendar_and_real_clock():
    result = run_tool(
        ToolCall(
            name="date_difference", arguments={"start": "2026-09-01", "end": "2026-09-25"}, reason="test"
        )
    )
    assert result["result"] == 24
    result = run_tool(ToolCall(name="current_time", arguments={"timezone": "Asia/Kolkata"}, reason="test"))
    assert result["ok"] and "+05:30" in result["result"]
