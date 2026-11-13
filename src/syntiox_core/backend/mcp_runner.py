import os
import sys
import ast
import json
import asyncio
import textwrap
from typing import Any, Dict, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from backend.config_paths import PACKAGE_DIR, MCP_SCHEMAS_DIR, MCP_CONFIG_FILE, CONFIG_DIR

BUILTIN_MCP_SERVERS: Dict[str, str] = {
    "google_calendar": os.path.join(PACKAGE_DIR, "mcp_servers", "google", "calendar_handlers.py"),
    "google_docs": os.path.join(PACKAGE_DIR, "mcp_servers", "google", "docs_handlers.py"),
    "google_drive": os.path.join(PACKAGE_DIR, "mcp_servers", "google", "drive_handlers.py"),
    "google_forms": os.path.join(PACKAGE_DIR, "mcp_servers", "google", "forms_handlers.py"),
    "google_gmail": os.path.join(PACKAGE_DIR, "mcp_servers", "google", "gmail_handlers.py"),
    "google_sheets": os.path.join(PACKAGE_DIR, "mcp_servers", "google", "sheets_handlers.py"),
    "google_slides": os.path.join(PACKAGE_DIR, "mcp_servers", "google", "slides_handlers.py"),
    "google_tasks": os.path.join(PACKAGE_DIR, "mcp_servers", "google", "tasks_handlers.py"),
    "math_solver": os.path.join(PACKAGE_DIR, "mcp_servers", "math", "math_solver_mcp.py"),
    "python_sandbox": os.path.join(PACKAGE_DIR, "mcp_servers", "sandbox", "python_sandbox_mcp.py"),
    "nodejs_sandbox": os.path.join(PACKAGE_DIR, "mcp_servers", "sandbox", "nodejs_sandbox_mcp.py"),
    "mouse_keyboard": os.path.join(PACKAGE_DIR, "mcp_servers", "desktop", "mouse_keyboard_mcp.py"),
}

SERVER_ALIASES: Dict[str, str] = {
    "calendar": "google_calendar",
    "docs": "google_docs",
    "drive": "google_drive",
    "forms": "google_forms",
    "gmail": "google_gmail",
    "sheets": "google_sheets",
    "slides": "google_slides",
    "tasks": "google_tasks",
    "math": "math_solver",
    "python": "python_sandbox",
    "nodejs": "nodejs_sandbox",
    "desktop": "mouse_keyboard",
    "mouse": "mouse_keyboard",
    "keyboard": "mouse_keyboard",
    "desktop_control": "mouse_keyboard",
}

_SCHEMA_INDEX_CACHE: Dict[str, List[str]] = {}
_LAST_CONFIG_MTIME: float = -1.0


def load_user_mcp_servers() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(MCP_CONFIG_FILE):
        return {}
    try:
        with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            servers = data.get("mcpServers", data)
            if isinstance(servers, dict):
                return {k: v for k, v in servers.items() if isinstance(v, dict) and "command" in v}
    except Exception as e:
        print(f"[MCP] Error reading {MCP_CONFIG_FILE}: {e}")
    return {}


def _load_mcp_permissions() -> dict:
    perm_path = os.path.join(CONFIG_DIR, "local", "mcp_permissions.json")
    if not os.path.exists(perm_path):
        return {}
    try:
        with open(perm_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_tool_permission(server_name: str, tool_name: str) -> str:
    perms = _load_mcp_permissions()
    server_perms = perms.get(server_name, {})
    if isinstance(server_perms, dict) and tool_name in server_perms:
        return server_perms[tool_name]
    if isinstance(server_perms, dict) and "_default" in server_perms:
        return server_perms["_default"]
    return perms.get("_default", "allow_ask")


def _update_mcp_permission(server_name: str, tool_name: str, permission: str):
    perm_path = os.path.join(CONFIG_DIR, "local", "mcp_permissions.json")
    perms = _load_mcp_permissions()
    if server_name not in perms:
        perms[server_name] = {}
    perms[server_name][tool_name] = permission
    try:
        with open(perm_path, "w", encoding="utf-8") as f:
            json.dump(perms, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[MCP] Failed to update permissions: {e}")


def _sync_mcp_permissions(index: Dict[str, List[str]]):
    """Auto-populates new servers/tools into mcp_permissions.json without overwriting existing settings."""
    perm_path = os.path.join(CONFIG_DIR, "local", "mcp_permissions.json")
    if not os.path.exists(perm_path):
        return
    perms = _load_mcp_permissions()
    changed = False

    for server_name, tools in index.items():
        if server_name not in perms:
            perms[server_name] = {"_default": "allow_process"}
            changed = True
        elif not isinstance(perms[server_name], dict):
            perms[server_name] = {"_default": perms[server_name]}
            changed = True

        for tool_name in tools:
            if tool_name not in perms[server_name]:
                perms[server_name][tool_name] = perms[server_name].get("_default", "allow_process")
                changed = True

    if changed:
        try:
            with open(perm_path, "w", encoding="utf-8") as f:
                json.dump(perms, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[MCP] Failed to auto-sync permissions: {e}")


def _map_annotation_type(annotation) -> str:
    if annotation and isinstance(annotation, ast.Name):
        if annotation.id == "int":
            return "integer"
        if annotation.id == "float":
            return "number"
        if annotation.id == "bool":
            return "boolean"
        if annotation.id == "dict":
            return "object"
        if annotation.id == "list":
            return "array"
    return "string"


def _eval_ast_str_or_obj(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Call) and node.args:
        inner = _eval_ast_str_or_obj(node.args[0])
        if isinstance(inner, str):
            return textwrap.dedent(inner).strip()
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _extract_python_mcp_schemas(server_name: str, script_path: str) -> List[Dict[str, Any]]:
    schemas: List[Dict[str, Any]] = []
    if not os.path.exists(script_path):
        return schemas
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception:
        return schemas

    # 1. FastMCP @mcp.tool() decorated functions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_mcp_tool = False
            for dec in node.decorator_list:
                dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                if "mcp.tool" in dec_str:
                    is_mcp_tool = True
                    break
            if not is_mcp_tool:
                continue

            properties: Dict[str, Any] = {}
            required: List[str] = []
            num_args = len(node.args.args)
            num_defaults = len(node.args.defaults)
            for i, arg in enumerate(node.args.args):
                arg_name = arg.arg
                if arg_name in ("self", "ctx"):
                    continue
                is_req = i < (num_args - num_defaults)
                arg_type = _map_annotation_type(arg.annotation)
                prop: Dict[str, Any] = {"type": arg_type, "description": f"Parameter '{arg_name}'."}
                if arg_type == "array":
                    prop["items"] = {"type": "string"}
                if not is_req:
                    default_idx = i - (num_args - num_defaults)
                    default_val = _eval_ast_str_or_obj(node.args.defaults[default_idx])
                    if default_val is not None:
                        prop["default"] = default_val
                properties[arg_name] = prop
                if is_req:
                    required.append(arg_name)

            doc = (ast.get_docstring(node) or f"Execute {node.name} on {server_name}.").strip()
            schemas.append({
                "server_name": server_name,
                "tool_name": node.name,
                "description": doc,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })

    # 2. Standard mcp.server.Server Tool(...) definitions inside @app.list_tools()
    if not schemas:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Tool":
                t_name = None
                t_desc = ""
                t_schema = {"type": "object", "properties": {}, "required": []}
                for kw in node.keywords:
                    if kw.arg == "name":
                        t_name = _eval_ast_str_or_obj(kw.value)
                    elif kw.arg == "description":
                        t_desc = _eval_ast_str_or_obj(kw.value) or ""
                    elif kw.arg == "inputSchema":
                        parsed = _eval_ast_str_or_obj(kw.value)
                        if isinstance(parsed, dict):
                            t_schema = parsed
                if t_name:
                    schemas.append({
                        "server_name": server_name,
                        "tool_name": str(t_name),
                        "description": str(t_desc).strip(),
                        "inputSchema": t_schema,
                    })

    return schemas


async def _fetch_external_mcp_schemas(server_name: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    cmd = cfg.get("command", "")
    args = cfg.get("args", [])
    env_vars = cfg.get("env")
    merged_env = None
    if isinstance(env_vars, dict):
        merged_env = os.environ.copy()
        for k, v in env_vars.items():
            merged_env[str(k)] = str(v)

    params = StdioServerParameters(command=cmd, args=list(args), env=merged_env)
    schemas: List[Dict[str, Any]] = []
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_res = await session.list_tools()
                for t in getattr(tools_res, "tools", []):
                    schemas.append({
                        "server_name": server_name,
                        "tool_name": t.name,
                        "description": (t.description or "").strip(),
                        "inputSchema": getattr(t, "inputSchema", {"type": "object", "properties": {}}),
                    })
    except Exception as e:
        print(f"[MCP] Failed to fetch tool schemas from external server '{server_name}': {e}")
    return schemas


def _run_coro_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    return asyncio.run(coro)


def sync_mcp_schemas(force: bool = False) -> Dict[str, List[str]]:
    """
    Auto-generates individual JSON tool schemas under MCP_SCHEMAS_DIR/<server_name>/<tool_name>.json
    for all built-in MCP servers and user-configured servers in mcp_servers.json.
    """
    global _SCHEMA_INDEX_CACHE, _LAST_CONFIG_MTIME
    cfg_mtime = os.path.getmtime(MCP_CONFIG_FILE) if os.path.exists(MCP_CONFIG_FILE) else 0.0
    if _SCHEMA_INDEX_CACHE and not force and cfg_mtime == _LAST_CONFIG_MTIME:
        return _SCHEMA_INDEX_CACHE

    os.makedirs(MCP_SCHEMAS_DIR, exist_ok=True)
    index: Dict[str, List[str]] = {}

    # 1. Built-in MCP servers
    for server_name, script_path in BUILTIN_MCP_SERVERS.items():
        server_schema_dir = os.path.join(MCP_SCHEMAS_DIR, server_name)
        os.makedirs(server_schema_dir, exist_ok=True)
        schemas = _extract_python_mcp_schemas(server_name, script_path)
        tool_names: List[str] = []
        for s in schemas:
            t_name = s["tool_name"]
            tool_names.append(t_name)
            json_path = os.path.join(server_schema_dir, f"{t_name}.json")
            if force or not os.path.exists(json_path):
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(s, f, indent=2, ensure_ascii=False)
        if tool_names:
            index[server_name] = tool_names

    # 2. User-configured external MCP servers in mcp_servers.json
    user_servers = load_user_mcp_servers()
    for server_name, cfg in user_servers.items():
        server_schema_dir = os.path.join(MCP_SCHEMAS_DIR, server_name)
        os.makedirs(server_schema_dir, exist_ok=True)
        existing_jsons = [f[:-5] for f in os.listdir(server_schema_dir) if f.endswith(".json")]
        if existing_jsons and not force and cfg_mtime == _LAST_CONFIG_MTIME:
            index[server_name] = sorted(existing_jsons)
            continue

        # Check if command points to a local python MCP script we can parse via AST first
        cmd = str(cfg.get("command", ""))
        args = cfg.get("args", [])
        schemas = []
        if ("python" in cmd.lower() or cmd == sys.executable) and args and str(args[0]).endswith(".py") and os.path.exists(str(args[0])):
            schemas = _extract_python_mcp_schemas(server_name, str(args[0]))
        if not schemas:
            schemas = _run_coro_sync(_fetch_external_mcp_schemas(server_name, cfg))

        tool_names = []
        for s in schemas:
            t_name = s["tool_name"]
            tool_names.append(t_name)
            json_path = os.path.join(server_schema_dir, f"{t_name}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2, ensure_ascii=False)
        if tool_names:
            index[server_name] = tool_names
        elif existing_jsons:
            index[server_name] = sorted(existing_jsons)

    _sync_mcp_permissions(index)

    _SCHEMA_INDEX_CACHE = index
    _LAST_CONFIG_MTIME = cfg_mtime
    return index


def get_mcp_prompt_summary() -> str:
    """
    Returns the lazy-loaded MCP servers summary block for the system prompt.
    """
    index = sync_mcp_schemas()
    if not index:
        return ""

    schemas_dir_norm = MCP_SCHEMAS_DIR.replace("\\", "/")
    lines = [
        "\n[AVAILABLE MCP SERVERS (LAZY-LOADED)]",
        f"Each MCP server has a schema directory at `{schemas_dir_norm}/<server_name>/<tool_name>.json`.",
        "For lazily-loaded MCP tools:",
        f"1. Read the corresponding JSON schema file (`{schemas_dir_norm}/<server_name>/<tool_name>.json`) using `view_file` to inspect its arguments and inputSchema.",
        "2. Call the tool using `call_mcp_tool(server_name=\"<server_name>\", tool_name=\"<tool_name>\", arguments={...})`.",
        ""
    ]
    for server_name, tools in index.items():
        visible_tools = [t for t in tools if get_tool_permission(server_name, t) != "off"]
        if not visible_tools:
            continue
        lines.append(f"# {server_name}")
        lines.append(f"Lazy tools: {', '.join(visible_tools)}")
    return "\n".join(lines) + "\n"


def _resolve_server_and_tool(server_name: str, tool_name: str) -> str:
    s_clean = (server_name or "").strip()
    if s_clean in SERVER_ALIASES:
        s_clean = SERVER_ALIASES[s_clean]

    user_servers = load_user_mcp_servers()
    if s_clean in BUILTIN_MCP_SERVERS or s_clean in user_servers:
        index = sync_mcp_schemas()
        if s_clean in index and tool_name in index[s_clean]:
            return s_clean

    # Auto-resolve server by tool_name if server_name was omitted or mismatched
    index = sync_mcp_schemas()
    for srv, t_list in index.items():
        if tool_name in t_list:
            return srv

    return s_clean


async def _async_call_mcp_params(server_params: StdioServerParameters, tool_name: str, arguments: Dict[str, Any]) -> str:
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return "\n".join([c.text for c in result.content if hasattr(c, "text")])
    except Exception as e:
        return f"MCP Execution Error: {str(e)}"


def call_mcp_server_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Resolves server_name from BUILTIN_MCP_SERVERS or mcp_servers.json and executes tool_name.
    """
    resolved_server = _resolve_server_and_tool(server_name, tool_name)

    # Permission check
    permission = get_tool_permission(resolved_server, tool_name)
    if permission == "off":
        return f"Error: MCP tool '{tool_name}' on server '{resolved_server}' is disabled by user permissions."

    if permission == "allow_ask":
        from backend import interaction_manager
        decision = interaction_manager.request_mcp_permission("main", resolved_server, tool_name, arguments or {})
        if decision == "skip":
            return f"Action skipped: User skipped MCP tool '{tool_name}'."
        if decision == "allow_always":
            _update_mcp_permission(resolved_server, tool_name, "allow_process")

    user_servers = load_user_mcp_servers()

    if resolved_server in BUILTIN_MCP_SERVERS:
        script_path = BUILTIN_MCP_SERVERS[resolved_server]
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[script_path],
            env=None,
        )
    elif resolved_server in user_servers:
        cfg = user_servers[resolved_server]
        cmd = cfg.get("command", "")
        args = list(cfg.get("args", []))
        env_vars = cfg.get("env")
        merged_env = None
        if isinstance(env_vars, dict):
            merged_env = os.environ.copy()
            for k, v in env_vars.items():
                merged_env[str(k)] = str(v)
        server_params = StdioServerParameters(command=cmd, args=args, env=merged_env)
    else:
        available = list(BUILTIN_MCP_SERVERS.keys()) + list(user_servers.keys())
        return f"Error: Unknown MCP server '{server_name}'. Available servers: {', '.join(available)}"

    try:
        return _run_coro_sync(_async_call_mcp_params(server_params, tool_name, arguments or {}))
    except Exception as e:
        return f"MCP Execution Error: {str(e)}"
