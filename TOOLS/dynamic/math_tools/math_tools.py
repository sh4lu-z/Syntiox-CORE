import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

@action_logger("math_solve")
def math_solve(action: str, expression: str, options: str = "") -> str:
    """
    Math solver: algebra, calculus, equations, factorial (y!), plots.
    action: 'solve', 'steps', or 'graph'.
    expression: math text; equations use = e.g. x**2 - y! = 2026
    options: solve/steps: 'integrate', 'solve', 'simplify'; graph: 'x_min=-10,x_max=10'
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "math_solver_mcp.py")
    return run_mcp_tool(server_path, "math_solve", {
        "action": action,
        "expression": expression,
        "options": options
    })
