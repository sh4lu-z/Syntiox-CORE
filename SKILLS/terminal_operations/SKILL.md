---
name: Terminal Operations
description: Triggers when the user asks to run commands, interact with the OS, or use PowerShell.
keywords: terminal, shell, command, powershell, cmd, system, run, open
---

1. TERMINAL OPERATIONS:
To run terminal commands safely, write Python code that uses the `subprocess` module.
Example:
```python
import subprocess
result = subprocess.run(["powershell", "-Command", "Get-Process"], capture_output=True, text=True)
print(result.stdout)
```
Ensure that any command you run is safe and will not destroy user data. Do not run infinite loops.
