# Syntiox CORE

<p align="center">
  <img src="logo.svg" alt="Syntiox CORE Logo" />
</p>

Syntiox CORE is an advanced Agentic AI system that dynamically routes intents, leverages context memory, and controls complex subsystems (such as an interactive browser subagent) to accomplish sophisticated tasks on behalf of the user.

## Features
- **Dynamic Intent Routing**: Intelligently routes tasks to the appropriate skills and subagents.
- **Context Memory**: Maintains context across sessions for highly personalized responses.
- **Interactive Browser Subagent**: Automates persistent web browsers natively without typical bot restrictions, complete with visual feedback loops.
- **Secure Architecture**: Environment variables and sensitive API keys are securely protected and not committed to source control.

## Getting Started

### Prerequisites
- Python 3.9+
- Playwright (installed and configured via `playwright install`)

### Installation (Windows Only)
Run the following PowerShell command to automatically install and configure Syntiox CORE:
```powershell
irm https://raw.githubusercontent.com/sh4lu-z/Syntiox-CORE/main/install.cmd -OutFile install.cmd ; .\install.cmd
```
The installer will set up your virtual environment, isolate configurations, and expose the `stx` global command.

### Usage
Once installed, you can launch the AI from anywhere in your terminal:
```bash
stx
```

To configure your Google login for integrated tools (Gmail, Drive, Calendar, etc.):
```bash
stx-google-login
```

*Note: The system source code is managed inside `%APPDATA%\.sh4lu-z\Syntiox CORE`, while your personal data (workspaces, chat history, and config) is stored safely in `%USERPROFILE%\.sh4lu-z\Syntiox CORE`.*

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
