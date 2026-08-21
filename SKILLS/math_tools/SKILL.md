---
name: Math Tools
description: Advanced math solver for algebra, calculus, equations, and graphing using MCP.
keywords: math, solve, calculate, equation, graph, algebra, calculus, plot, math solver, integrate, differentiate
---

# Math Tools Skill (MCP)
You have the ability to solve complex mathematical problems and draw graphs using the `mcp_runner` helper.
When the user asks you to solve math or plot a graph, you MUST write a python script to execute it.

**IMPORTANT:** 
1. Use `sys.path.append(r"{ROOT_DIR}")` (since code runs in the workspace folder) to ensure `backend.mcp_runner` can be imported.
2. The MCP server path is `MCP/math_solver_mcp.py` (relative to the project root).

## Available Tool:
1. **`math_solve`**:
   - Arguments:
     - `action` (string): 'solve', 'steps', or 'graph'
     - `expression` (string): The math expression (e.g., 'x**2 = 4', 'sin(x), cos(x)')
     - `options` (string): 'solve', 'integrate', 'differentiate', 'simplify', 'factor', 'expand', or graph options like 'x_min=-10,x_max=10'

### Code Example for Solving an Equation:
```python
import sys
sys.path.append(r"{ROOT_DIR}")
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(r"{ROOT_DIR}", "MCP", "math_solver_mcp.py"),
    "math_solve",
    {
        "action": "solve",
        "expression": "integrate(x**2, x, 0, 1)",
        "options": "integrate"
    }
)
print(result)
```

### Code Example for Plotting a Graph:
```python
import sys
sys.path.append(r"{ROOT_DIR}")
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(r"{ROOT_DIR}", "MCP", "math_solver_mcp.py"),
    "math_solve",
    {
        "action": "graph",
        "expression": "sin(x); cos(x)",
        "options": "x_min=-10,x_max=10"
    }
)
print(result)
```
