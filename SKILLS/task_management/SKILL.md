---
name: Task Management
description: Triggers for large projects, complex multi-step tasks, planning, and creating documentation.
keywords: plan, project, large, complex, task, walkthrough, readme, build, create, step, continue, next, start
---

1. PLANNING & TASK MANAGEMENT:
CRITICAL RULE: DO NOT use `task.md` or planning steps for simple, single-step tasks (e.g., checking RAM, viewing a file, running a quick command, answering a question). For simple tasks, JUST DO IT and reply.
ONLY if the user explicitly asks for a large, complex, multi-step project (e.g., "build a full website", "deploy a multi-tier app"), your first action MUST be to use the `create_project_brain` tool (e.g. `{"name": "create_project_brain", "arguments": {"project_name": "my_project"}}`).
- The tool will return an absolute path to a new `brain` folder for this project. You MUST create and save your `task.md` file inside this exact returned path.
- Inside `task.md`, break down the work into smaller steps using markdown checkboxes: `- [ ] step 1`.
- If the user asks you to "continue" or "take the next step", use Python or `view_file` to read the `task.md` from the current project's brain folder.
- As you complete a task, read `task.md`, mark it as `- [x]`, and write it back to the brain folder.
- AUTOMATIC LOOP: You are an autonomous agent. When you finish a step, output `[NEXT_STEP_REQUIRED]` to immediately start the next step. Do not stop until all tasks are done.
- When ALL tasks are finished, generate a walkthrough. **CRITICAL:** Save this as `walkthrough.md` inside the brain folder alongside `task.md`. Combine any older walkthrough data if you are updating an existing project.
- **FINAL DESTINATION & CLEANUP**: Save the actual project code to the user's requested absolute path. You can use the brain folder for scratch files, but delete them when done, leaving only `walkthrough.md` and `task.md`.
- ONLY when `walkthrough.md` is saved, output `[TASK_COMPLETE] I have finished the project. Please check the walkthrough.` to exit Agent Mode.
