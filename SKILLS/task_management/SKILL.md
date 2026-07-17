---
name: Task Management
description: Triggers for large projects, complex multi-step tasks, planning, and creating documentation.
keywords: plan, project, large, complex, task, walkthrough, readme, build, create, step, continue, next, start
---

1. PLANNING & TASK MANAGEMENT:
If the user gives you a large or multi-step task, your first action MUST be to create a `task.md` file.
- Inside `task.md`, break down the work into smaller steps using markdown checkboxes: `- [ ] step 1`.
- If the user asks you to "continue" or "take the next step", use Python to read `task.md` first.
- As you complete a task, read `task.md`, mark it as `- [x]`, and write it back.
- AUTOMATIC LOOP: You are an autonomous agent. When you finish a step, output `[NEXT_STEP_REQUIRED]` to immediately start the next step. Do not stop until all tasks are done.
- When ALL tasks are finished, generate a walkthrough. **CRITICAL:** If `walkthrough.md` already exists, you MUST read it first. Then, combine your new walkthrough with the existing one into a single, highly cohesive document. The final combined document MUST NOT exceed 1500 characters. Summarize older information if necessary. Overwrite `walkthrough.md` with this combined summary.
- **FINAL DESTINATION & CLEANUP**: If the user specified an absolute path to save the final project (e.g. `D:\projects\...`), you MUST save the final deliverables to that requested absolute path. You can use `workspace/` for temporary scratch files, but as your very last step, you must use Python `os.remove` to delete any temporary scratch files you created in `workspace/` (except `walkthrough.md` and `task.md`), keeping the workspace clean.
- ONLY when `walkthrough.md` is saved and files are in their final destination, output `[TASK_COMPLETE] I have finished the project. Please check the walkthrough.` to exit Agent Mode and return to Chat.
