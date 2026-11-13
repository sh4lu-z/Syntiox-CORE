# Syntiox CORE User Guides

This document provides setup instructions for extending Syntiox CORE with custom MCP servers and domain skills.

---

## 1. Adding Custom MCP Servers

Syntiox CORE supports the Model Context Protocol (MCP) using a lazy-loaded architecture. Built-in servers (Google Workspace, Math Solver, Python/Node.js sandboxes) and external user MCP servers are registered automatically.

### Configuration File
User-defined MCP servers are configured in:
```text
%USERPROFILE%\.sh4lu-z\Syntiox CORE\config\local\mcp_servers.json
```
An example configuration file is located at `config/examples/mcp_servers.json`.

### Configuration Format
Syntiox CORE uses the standard MCP JSON format (compatible with Claude Desktop, Cursor, and Antigravity):

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "C:\\data\\test.db"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxxxxxxxxxx"
      }
    },
    "custom_python": {
      "command": "python",
      "args": ["C:\\tools\\my_mcp_server.py"]
    }
  }
}
```

### Configuration Fields
- `command`: The executable used to start the MCP server process (`python`, `uvx`, `npx`, `node`, or an absolute executable path).
- `args`: Array of command-line arguments passed to the server.
- `env`: Optional dictionary of environment variables passed to the server process.

### How Lazy Schema Discovery Works
1. On server startup or when `mcp_servers.json` changes, Syntiox CORE inspects each configured MCP server.
2. For Python-based scripts, tool definitions are extracted via fast AST parsing. For external packages or binary servers, it connects via stdio and queries `list_tools`.
3. Individual JSON schemas for discovered tools are saved under:
   ```text
   %USERPROFILE%\.sh4lu-z\Syntiox CORE\mcp_schemas\<server_name>\<tool_name>.json
   ```
4. The system prompt receives a compact index of available servers and tool names without dumping large schemas into the prompt.
5. When the agent needs a specific tool, it reads `<tool_name>.json` using `view_file` to inspect required arguments, then invokes `call_mcp_tool(server_name, tool_name, arguments)`.

### Built-in MCP Servers
- `google_calendar`: Events management and reminders
- `google_docs`: Document creation, editing, and content extraction
- `google_drive`: File and folder management, sharing, and downloads
- `google_forms`: Form creation and response inspection
- `google_gmail`: Email sending, search, drafts, and label management
- `google_sheets`: Spreadsheet reading and cell manipulation
- `google_slides`: Slide presentation generation and editing
- `google_tasks`: Task lists and todo management
- `math_solver`: Symbolic math, calculus, and equation solving via SymPy
- `python_sandbox`: Isolated Python code execution
- `nodejs_sandbox`: Isolated JavaScript/Node.js execution

---

## 2. Creating Custom Skills

Skills guide the agent through specialized domains (such as Git workflows, document extraction, or database migrations) without flooding the system prompt.

### Skills Directory
Skills are stored in:
```text
%USERPROFILE%\.sh4lu-z\Syntiox CORE\skills\
```
Default skills are shipped in `src/syntiox_core/skills/` and automatically copied to the user data directory on startup.

### Structure of a Skill
Each skill is a dedicated folder containing a `SKILL.md` file:
```text
skills/
  ├── core_thinking/
  │   └── SKILL.md
  ├── context_memory/
  │   └── SKILL.md
  ├── developer_git/
  │   └── SKILL.md
  ├── document_processing/
  │   └── SKILL.md
  ├── semantic_search/
  │   └── SKILL.md
  └── task_management/
      └── SKILL.md
```

### Creating a Skill
To create a new skill, create a folder under `skills/` with a `SKILL.md` file:

```markdown
---
name: Database Migrations
description: Use when the user asks for database schema migrations, SQL scripts, or ORM updates.
keywords: sql, database, migration, postgres, sqlite, alembic, schema
---

# Database Migration Guidelines

When writing database migrations:
1. Always check existing schema files before generating migration scripts.
2. Ensure rollback operations are defined for every migration step.
3. Test the script against a local SQLite database or staging environment before execution.
```

### Frontmatter Fields
- `name`: Human-readable name of the skill.
- `description`: A 1-sentence description explaining when the agent should use this skill.
- `keywords`: Comma-separated list of keywords.
  - If `keywords` contains `always` or `default`, the skill's full text is injected into the agent's base system prompt (`core_thinking`, `context_memory`).
  - Otherwise, the skill is registered as **on-demand**.

### How On-Demand Skills Work
1. On startup, all `SKILL.md` files are scanned and indexed.
2. Only `always`/`default` skills have their full content placed in the initial prompt.
3. All other skills are presented in the prompt as a lightweight index:
   ```text
   [AVAILABLE ON-DEMAND SKILLS]
   - developer_git (C:/.../skills/developer_git/SKILL.md): Use when the user asks for coding help, debugging, git commands...
   ```
4. When a task requires a specific skill, the agent reads its instructions using `view_file` on the provided path before continuing execution.

---

## 3. Customizing Global Agent Rules (SYNTIOX_CORE.md)

You can define project-wide rules, coding standards, and behavioral constraints for the agent.

### Configuration File
```text
%USERPROFILE%\.sh4lu-z\Syntiox CORE\config\prompts\SYNTIOX_CORE.md
```

### Usage & Word Limit
- Content written here is automatically injected into the agent's system prompt under `[USER GLOBAL RULES]`.
- Loaded up to a **2,000-word limit**. Content beyond 2,000 words is truncated at the word boundary to prevent context window overflow while preserving formatting.
