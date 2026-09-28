"""Small allowlisted tools. Calculator parses arithmetic; never executes user code."""

import ast
import math
import operator
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TOOLS_DESCRIPTION = """
calculator: arguments {expression: string}; arithmetic + - * / // % ** and parentheses only.
Percentages must be expressed as /100. No variables, functions or code.
current_time: arguments {timezone: IANA timezone string}, e.g. Asia/Kolkata or UTC.
date_difference: arguments {start: YYYY-MM-DD, end: YYYY-MM-DD}; signed calendar days end-start.
Use only numeric operands supported by the question or retrieved evidence. Do not invent operands.
No web browsing, weather, shell, file access or other external tools are available.
"""


def calculate(expression):
    """Evaluate bounded numeric arithmetic using an AST allowlist, never eval.

    Accept arithmetic operators and parentheses only. Bound expression length,
    node count, exponents, and intermediate values before returning a number.
    Invalid syntax, forbidden constructs, or arithmetic failures raise errors
    that ``run_tool`` converts into inspectable failure results.
    """
    if len(expression) > 200:
        raise ValueError("Expression is too long.")
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) > 60:
        raise ValueError("Expression is too complex.")
    binary = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    def evaluate(node):
        """Recursively evaluate an allowed node and validate its numeric result."""
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in binary:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise ValueError("Exponent must be between -12 and 12.")
            value = binary[type(node.op)](left, right)
        else:
            raise ValueError("Only numeric arithmetic is allowed.")
        if isinstance(value, complex) or not math.isfinite(value) or abs(value) > 1e15:
            raise ValueError("Result is outside the supported finite range (±1e15).")
        return value

    return evaluate(tree.body)


def run_tool(call):
    """Execute a validated ToolCall and return its arguments plus outcome metadata.

    Dispatch to the calculator, IANA-zone clock, or ISO date difference. Expected
    input and arithmetic failures return ``ok=False`` and an error string, so the
    execution agent can explain them without treating errors as computed answers.
    """
    try:
        args = call.arguments
        if call.name == "calculator":
            if set(args) != {"expression"}:
                raise ValueError("calculator requires only expression.")
            result = calculate(args["expression"])
        elif call.name == "current_time":
            if set(args) - {"timezone"}:
                raise ValueError("current_time accepts only timezone.")
            result = datetime.now(ZoneInfo(args.get("timezone", "UTC"))).isoformat()
        elif call.name == "date_difference":
            if set(args) != {"start", "end"}:
                raise ValueError("date_difference requires start and end.")
            result = (date.fromisoformat(args["end"]) - date.fromisoformat(args["start"])).days
        else:
            raise ValueError("Tool is not allowed.")
        return {**call.model_dump(), "ok": True, "result": result}
    except (ValueError, SyntaxError, ArithmeticError, TypeError, ZoneInfoNotFoundError) as exc:
        return {**call.model_dump(), "ok": False, "error": str(exc)[:250]}
