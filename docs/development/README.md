# Syntiox CORE Developer Guide

This guide covers setting up your local development environment, running tests, adding tools, and contributing to Syntiox CORE.

---

## 1. Development Environment Setup

### Prerequisites
- **Windows OS** (Syntiox CORE runtime is optimized for Windows PowerShell/CMD environments).
- **Python 3.9+**
- **Git**

### Installation
Clone the repository and install dependencies in editable mode:

```powershell
git clone https://github.com/sh4lu-z/Syntiox-CORE.git
cd "Syntiox CORE"
pip install -r requirements.txt
pip install -e .
```

### Local Configuration
Configuration files reside in `%USERPROFILE%\.sh4lu-z\Syntiox CORE\config\local\`:
- `.env`: API keys (`GEMINI_API_KEY`, `GROQ_API_KEY`) and model selectors.
- `mcp_servers.json`: External MCP server registrations.
- `credentials.json`: Google Cloud OAuth credentials (optional, for Google Workspace tools).

---

## 2. Running Syntiox CORE

### Start Backend Server Directly
```powershell
python -m syntiox_core.server
```

For CLI commands (`stx`, `stx --background`, `stx --logs`, `stx --stop`), see [Usage in README](../../README.md#usage).

---

## 3. Testing

All test suites and verification scripts belong inside the `test/` folder. Do not place temporary test scripts in the project root.

### Running Test Suites
```powershell
# Architecture, lazy MCP schema discovery, and tool tests
python test/test_mcp_and_skills_architecture.py

# Official SDK error handling and key rotation tests
python test/test_llm_error_handling.py
```

---

## 4. Adding Core Tools

All native tools are located in `src/syntiox_core/tools/core/`.

### Tool Conventions
1. **Logging**: Wrap public tool functions with `@action_logger("tool_name")` from `tools.core.logger`.
2. **Type Annotations**: Provide explicit type annotations (`str`, `int`, `float`, `bool`, `list`, `dict`) so `tools_loader.py` can generate proper function calling schemas.
3. **Docstrings**: Provide a clear docstring explaining what the function does and what each parameter represents.
4. **Safety & Approvals**: For destructive actions (e.g. system commands, outside-workspace file deletions), ensure `backend/executor.py` (`analyze_tool_call`) includes appropriate security checks.

Example:
```python
from tools.core.logger import action_logger

@action_logger("my_utility")
def my_utility(target_path: str, count: int = 1) -> str:
    """
    Performs a specific utility task.
    
    Args:
        target_path: Path to the target file.
        count: Number of iterations.
    """
    # Tool implementation
    return "Success"
```

---

## 5. Adding Built-in MCP Servers

Built-in MCP servers are located in `src/syntiox_core/mcp_servers/`.

1. Place your MCP server script in an appropriate subfolder under `src/syntiox_core/mcp_servers/` (e.g. `google/`, `sandbox/`, or a new folder).
2. Register the server in `BUILTIN_MCP_SERVERS` inside `src/syntiox_core/backend/mcp_runner.py`:
   ```python
   BUILTIN_MCP_SERVERS["my_server"] = os.path.join(PACKAGE_DIR, "mcp_servers", "my_category", "my_server_mcp.py")
   ```
3. Run `sync_mcp_schemas()` or run the test suite to verify that schema files are automatically generated under `mcp_schemas/my_server/`.

---

## 6. Git & Branching Workflow

Syntiox CORE is maintained in a public repository with protected branches.

1. **Always work on a feature branch**:
   ```powershell
   git checkout -b feature/<feature-name>
   ```
   Do not commit directly to `master`.
2. **Review staged files before committing**:
   Ensure temporary files, local `.env`, or credential tokens are never committed.
3. **Run tests before pushing**:
   Ensure all unit tests in `test/` pass cleanly.
