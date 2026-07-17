"""
Safe math parsing and SymPy operations for MathSolver MCP.
No arbitrary Python execution — expressions go through SymPy's parser only.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable

import sympy as sp
from sympy import Matrix
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

MATH_TIMEOUT_SEC = 10
_executor = ThreadPoolExecutor(max_workers=2)

_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

_FORBIDDEN = re.compile(
    r"(?:__\w+__|\bimport\b|\bexec\b|\beval\b|\bopen\b|\bcompile\b|"
    r"\bglobals\b|\blocals\b|\bgetattr\b|\bsetattr\b|\bos\b|\bsys\b|\bsubprocess\b)",
    re.IGNORECASE,
)

# Only SymPy-safe names; parse_expr uses this as local_dict (no builtins).
_SAFE_LOCALS: dict[str, Any] = {
    "Symbol": sp.Symbol,
    "symbols": sp.symbols,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "cot": sp.cot,
    "sec": sp.sec,
    "csc": sp.csc,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "sqrt": sp.sqrt,
    "abs": sp.Abs,
    "Abs": sp.Abs,
    "pi": sp.pi,
    "E": sp.E,
    "I": sp.I,
    "oo": sp.oo,
    "Matrix": Matrix,
    "integrate": sp.integrate,
    "diff": sp.diff,
    "Derivative": sp.Derivative,
    "Integral": sp.Integral,
    "solve": sp.solve,
    "simplify": sp.simplify,
    "expand": sp.expand,
    "factor": sp.factor,
    "limit": sp.limit,
    "Sum": sp.Sum,
    "Product": sp.Product,
    "factorial": sp.factorial,
    "factorial2": sp.factorial2,
}


def _convert_factorial(s: str) -> str:
    """y! -> factorial(y), 5! -> factorial(5), (n+1)! -> factorial(n+1). Keeps !=, <=, >=."""
    s = s.replace("!=", "__NEQ__")
    s = s.replace("<=", "__LEQ__")
    s = s.replace(">=", "__GEQ__")

    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"(\d+)!", r"factorial(\1)", s)
        s = re.sub(r"([a-zA-Z_][a-zA-Z0-9_]*)!", r"factorial(\1)", s)
        s = re.sub(r"\(([^()]+)\)!", r"factorial(\1)", s)

    return s.replace("__NEQ__", "!=").replace("__LEQ__", "<=").replace("__GEQ__", ">=")


def _split_equation(expr: str) -> tuple[str, str] | None:
    """Split on a single '=' (equation), not ==, !=, <=, >=."""
    s = expr.strip()
    if any(tok in s for tok in ("==", "!=", "<=", ">=")):
        return None
    if "=" not in s:
        return None
    idx = s.index("=")
    left, right = s[:idx].strip(), s[idx + 1 :].strip()
    if not left or not right:
        raise ValueError("Equation must have both sides of '='.")
    return left, right


def _normalize_notation(expr: str) -> str:
    """Convert common math notation to SymPy-friendly text."""
    s = expr.strip()
    if not s:
        raise ValueError("Expression is empty.")
    if _FORBIDDEN.search(s):
        raise ValueError("Expression contains forbidden tokens.")

    s = s.replace("^", "**")
    s = _convert_factorial(s)
    # 2x, 3sin(x) -> implicit multiplication (parser transform handles much of this)
    s = re.sub(r"(\d)([a-zA-Z(])", r"\1*\2", s)
    s = re.sub(r"\)(\s*)([a-zA-Z(])", r")*\1\2", s)
    return s


def parse_math(expr: str) -> sp.Basic:
    """Parse standard math notation into a SymPy object."""
    split = _split_equation(expr)
    if split is not None:
        left, right = split
        return sp.Eq(parse_math(left), parse_math(right))
    normalized = _normalize_notation(expr)
    try:
        return parse_expr(
            normalized,
            transformations=_TRANSFORMATIONS,
            local_dict=_SAFE_LOCALS.copy(),
            evaluate=True,
        )
    except Exception as e:
        raise ValueError(f"Could not parse expression: {e}") from e


def _run_with_timeout(fn: Callable[[], Any], timeout: float = MATH_TIMEOUT_SEC) -> Any:
    future = _executor.submit(fn)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeout as e:
        raise TimeoutError(
            f"Math operation timed out after {timeout:.0f} seconds."
        ) from e


def _detect_command(expression: str) -> tuple[str, str]:
    """If expression looks like integrate(...), return (operation, inner)."""
    patterns = [
        (r"^integrate\s*\(\s*(.+)\s*\)\s*$", "integrate"),
        (r"^diff(?:erentiate)?\s*\(\s*(.+)\s*\)\s*$", "differentiate"),
        (r"^solve\s*\(\s*(.+)\s*\)\s*$", "solve"),
        (r"^simplify\s*\(\s*(.+)\s*\)\s*$", "simplify"),
        (r"^factor\s*\(\s*(.+)\s*\)\s*$", "factor"),
        (r"^expand\s*\(\s*(.+)\s*\)\s*$", "expand"),
    ]
    for pat, op in patterns:
        m = re.match(pat, expression.strip(), re.IGNORECASE | re.DOTALL)
        if m:
            return op, m.group(1).strip()
    return "auto", expression.strip()


def _split_integrate_args(inner: str) -> tuple[str, str, str | None, str | None]:
    """
    Parse 'x**2*sin(x), x' or 'x**2, x, 0, 1' (comma at top level only).
    """
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in inner:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    if len(parts) < 2:
        raise ValueError("integrate needs at least: expression, variable")
    var = parts[1]
    lo = parts[2] if len(parts) > 2 else None
    hi = parts[3] if len(parts) > 3 else None
    return parts[0], var, lo, hi


def _split_two_args(inner: str) -> tuple[str, str]:
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in inner:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    if len(parts) < 2:
        raise ValueError("Need expression and variable separated by comma.")
    return parts[0], parts[1]


def _has_factorial(expr: sp.Basic) -> bool:
    return expr.has(sp.factorial)


def _is_perfect_square(n: int) -> tuple[bool, int]:
    if n < 0:
        return False, 0
    r = int(sp.sqrt(n))
    if r * r == n:
        return True, r
    return False, 0


def _solve_integer_factorial(eq: sp.Equality) -> str | None:
    """
    Brute-force integer search when the equation contains factorial(...).
    """
    if not _has_factorial(eq):
        return None

    syms = sorted(eq.free_symbols, key=str)
    if len(syms) != 2:
        return None

    residual = eq.lhs - eq.rhs
    results: list[str] = []
    y_sym, x_sym = syms[1], syms[0] if str(syms[0]) == "x" else syms[0]
    # Prefer symbol named y for outer factorial loop
    if str(syms[0]) == "y":
        y_sym, x_sym = syms[0], syms[1]

    for y_val in range(0, 30):
        sub_y = residual.subs(y_sym, y_val)
        for x_val in range(-250, 251):
            val = sub_y.subs(x_sym, x_val)
            if val == 0 or (val.is_Number and abs(int(val)) < 1):
                results.append(f"{x_sym} = {x_val}, {y_sym} = {y_val}")

    if not results:
        return (
            "No integer solutions found (x in [-250,250], y in [0,29]). "
            "Try rewriting, e.g. factorial(y) instead of y!."
        )

    seen: set[str] = set()
    unique = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return "Integer solutions:\n" + "\n".join(unique)


def _solve_equation(eq: sp.Basic, var_name: str | None) -> str:
    if not isinstance(eq, sp.Equality):
        eq = sp.Eq(eq, 0)

    if _has_factorial(eq):
        special = _solve_integer_factorial(eq)
        if special:
            return special

    syms = sorted(eq.free_symbols, key=lambda s: str(s))
    if var_name:
        var = sp.Symbol(var_name)
        solutions = sp.solve(eq, var)
    elif len(syms) == 1:
        solutions = sp.solve(eq, syms[0])
    elif len(syms) >= 2:
        solutions = sp.solve(eq, syms)
    else:
        return "No variables found in equation."

    if not solutions:
        if _has_factorial(eq):
            special = _solve_integer_factorial(eq)
            if special:
                return special
        return "No solutions found."

    if isinstance(solutions, dict):
        lines = [f"{k} = {sp.pretty(v)}" for k, v in solutions.items()]
        return "\n".join(lines)
    if isinstance(solutions, list) and solutions and isinstance(solutions[0], dict):
        lines = []
        for i, sol in enumerate(solutions, 1):
            lines.append(f"Solution {i}: " + ", ".join(f"{k}={v}" for k, v in sol.items()))
        return "\n".join(lines)
    if len(solutions) == 1:
        return sp.pretty(solutions[0])
    return "\n".join(sp.pretty(s) for s in solutions)


def execute_math(expression: str, operation_type: str = "auto") -> str:
    """Run symbolic math and return a formatted string result."""
    op = (operation_type or "auto").strip().lower()
    expr_raw = expression.strip()

    if op == "auto":
        detected, inner = _detect_command(expr_raw)
        if detected != "auto":
            op = detected
            expr_raw = inner

    def _work() -> str:
        nonlocal op, expr_raw

        if op == "simplify":
            return sp.pretty(sp.simplify(parse_math(expr_raw)))

        if op == "auto":
            parsed = parse_math(expr_raw)
            if isinstance(parsed, sp.Equality):
                return _solve_equation(parsed, None)
            result = sp.simplify(parsed)
            return sp.pretty(result)

        if op in ("differentiate", "diff", "derivative"):
            if "," in expr_raw:
                body, var_name = _split_two_args(expr_raw)
            else:
                body, var_name = expr_raw, "x"
            var = sp.Symbol(var_name)
            result = sp.diff(parse_math(body), var)
            return sp.pretty(result)

        if op == "integrate":
            body_s, var_name, lo_s, hi_s = _split_integrate_args(expr_raw)
            var = sp.Symbol(var_name)
            body = parse_math(body_s)
            if lo_s is not None and hi_s is not None:
                lo = parse_math(lo_s)
                hi = parse_math(hi_s)
                result = sp.integrate(body, (var, lo, hi))
            else:
                result = sp.integrate(body, var)
            return sp.pretty(result)

        if op == "solve":
            if _split_equation(expr_raw) is not None:
                return _solve_equation(parse_math(expr_raw), None)
            if "," in expr_raw:
                eq_s, var_name = _split_two_args(expr_raw)
                return _solve_equation(parse_math(eq_s), var_name)
            return _solve_equation(parse_math(expr_raw), None)

        if op == "factor":
            return sp.pretty(sp.factor(parse_math(expr_raw)))

        if op == "expand":
            return sp.pretty(sp.expand(parse_math(expr_raw)))

        if op == "evaluate":
            val = parse_math(expr_raw)
            if val.free_symbols:
                simplified = sp.simplify(val)
                return f"{sp.pretty(simplified)}\n(numeric: {simplified.evalf()})"
            return str(val.evalf())

        if op in ("determinant", "det"):
            m = parse_math(expr_raw)
            if not isinstance(m, Matrix):
                m = Matrix(m)
            return sp.pretty(m.det())

        if op in ("inverse", "inv"):
            m = parse_math(expr_raw)
            if not isinstance(m, Matrix):
                m = Matrix(m)
            return sp.pretty(m.inv())

        if op == "matrix_multiply":
            parts = [p.strip() for p in expr_raw.split("||")]
            if len(parts) != 2:
                raise ValueError("matrix_multiply: use 'A || B' for two matrices.")
            a = parse_math(parts[0])
            b = parse_math(parts[1])
            if not isinstance(a, Matrix):
                a = Matrix(a)
            if not isinstance(b, Matrix):
                b = Matrix(b)
            return sp.pretty(a * b)

        raise ValueError(
            f"Unknown operation_type '{operation_type}'. "
            "Use: simplify, differentiate, integrate, solve, factor, expand, "
            "evaluate, determinant, inverse, matrix_multiply, or auto."
        )

    return _run_with_timeout(_work)


def sympy_steps_fallback(expression: str, operation_type: str, result: str) -> str:
    """Human-readable fallback when Wolfram API is unavailable."""
    return (
        f"📐 ප්‍රශ්නය: {expression}\n"
        f"🔧 මෙහෙයුම: {operation_type}\n"
        f"{'═' * 45}\n"
        f"✅ SymPy සත්‍යාපිත අවසාන පිළිතුර:\n{result}\n"
        f"{'═' * 45}\n"
        f"📝 පියවරෙන් පියවර විසඳුම:\n"
        f"Wolfram Alpha API key (.env) නැත. "
        f"මෙම verified answer එක ආරම්භක සත්‍යය ලෙස ගෙන, "
        f"ප්‍රශ්නයේ සිට අවසාන පිළිතුර දක්වා සිංහලෙන් පියවර පැහැදිලි කරන්න."
    )
