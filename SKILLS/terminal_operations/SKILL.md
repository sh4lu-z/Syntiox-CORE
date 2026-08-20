---
name: Terminal Operations
description: Triggers when the user asks to run commands, interact with the OS, or use PowerShell.
keywords: terminal, shell, command, powershell, cmd, system, run, open
---

1. TERMINAL OPERATIONS:
To run terminal commands safely and easily, invoke the `run_terminal_command` native tool.
Ensure that any command you run is safe and will not destroy user data. Do not run infinite loops.

2. BACKGROUND PROCESSES:
If you need to start a long-running process like a web server, development server (e.g., node, python -m http.server), or any command that does not exit immediately, ALWAYS use the `run_background_command` tool.
- Never use `run_terminal_command` for servers, as it will block execution and crash the agent loop.
- You can manage spawned background tasks using the `manage_task` tool (actions: 'list', 'status', 'kill', 'send_input').
