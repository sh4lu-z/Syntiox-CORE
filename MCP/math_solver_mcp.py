#!/usr/bin/env python3
"""
MathSolver MCP — LM Studio compatible (manual tool schemas, string-only params).
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import re
import textwrap
from typing import Any

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("math-solver")

# LM Studio Jinja breaks on boolean/number/anyOf in tool schemas — strings only, no defaults.


def _parse_options(options: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (options or "").split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


def _wolfram_steps(query: str) -> str | None:
    app_id = os.getenv("WOLFRAM_ALPHA_APPID", "").strip()
    if not app_id:
        return None
    try:
        resp = requests.get(
            "https://api.wolframalpha.com/v2/query",
            params={
                "input": query,
                "appid": app_id,
                "format": "plaintext",
                "output": "JSON",
                "podstate": "Result__Step-by-step solution",
            },
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    chunks: list[str] = []
    for pod in data.get("queryresult", {}).get("pods", []):
        title = (pod.get("title") or "").lower()
        if "step" in title or title == "result":
            for sub in pod.get("subpods", []):
                t = (sub.get("plaintext") or "").strip()
                if t:
                    chunks.append(t)
    return "\n\n".join(chunks) if chunks else None


def _graph(expression: str, options: str) -> str:
    from math_utils import parse_math

    opts = _parse_options(options)
    fn_list = [f.strip() for f in expression.split(";") if f.strip()]
    if not fn_list:
        fn_list = [f.strip() for f in expression.split(",") if f.strip()]
    if not fn_list:
        return "Error: no functions to plot."

    xmin = float(opts.get("x_min", "-10"))
    xmax = float(opts.get("x_max", "10"))
    if xmin >= xmax:
        return "Error: x_min must be less than x_max."

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import sympy as sp

    x = np.linspace(xmin, xmax, 500)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    try:
        for fn in fn_list:
            expr = parse_math(fn)
            f_lambda = sp.lambdify(sp.Symbol("x"), expr, modules=["numpy"])
            ax.plot(x, f_lambda(x), label=fn, linewidth=2)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        if opts.get("use_y_limit", "").lower() in ("1", "true", "yes"):
            ax.set_ylim(float(opts.get("y_min", "0")), float(opts.get("y_max", "1")))
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("ascii")
        return (
            f"Graph OK ({len(fn_list)} curves), x from {xmin} to {xmax}\n"
            f"data:image/png;base64,{b64}"
        )
    except Exception as e:
        plt.close("all")
        return f"Graph error: {e}"


def _solve(action: str, expression: str, options: str) -> str:
    from dotenv import load_dotenv
    import os
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))
    from math_utils import execute_math, sympy_steps_fallback

    op = (options.strip() or "auto") if action in ("solve", "steps") else "auto"
    if action == "solve":
        try:
            result = execute_math(expression, op)
            return f"Result ({op}):\n{result}"
        except TimeoutError as e:
            return f"Timeout: {e}"
        except Exception as e:
            return f"Math error: {e}"

    if action == "steps":
        try:
            verified = execute_math(expression, op)
        except Exception as e:
            return f"Could not verify: {e}"
        wolfram = _wolfram_steps(expression)
        if wolfram:
            return f"Wolfram steps:\n{wolfram}\n\nSymPy check:\n{verified}"
        return sympy_steps_fallback(expression, op, verified)

    if action == "graph":
        return _graph(expression, options)

    return f"Unknown action '{action}'. Use solve, steps, or graph."


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="math_solve",
            description=textwrap.dedent("""\
                Math solver: algebra, calculus, equations, factorial (y!), plots.
                action: solve, steps, or graph.
                expression: math text; equations use = e.g. x**2 - y! = 2026
                  (y! means factorial(y)); also x^2 and integrate forms.
                options: solve/steps: integrate, solve, simplify; graph: x_min=-10,x_max=10
            """),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "solve, steps, or graph",
                    },
                    "expression": {
                        "type": "string",
                        "description": "Math expression or comma-separated functions for graph",
                    },
                    "options": {
                        "type": "string",
                        "description": "Operation name or graph options key=value comma list",
                    },
                },
                "required": ["action", "expression"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name != "math_solve":
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    action = str(arguments.get("action", "solve")).strip().lower()
    expression = str(arguments.get("expression", "")).strip()
    options = str(arguments.get("options", "")).strip()

    if not expression:
        return [TextContent(type="text", text="Error: expression is required.")]

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _solve, action, expression, options)
    return [TextContent(type="text", text=result)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
