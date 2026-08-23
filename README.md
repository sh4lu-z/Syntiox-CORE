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
- **Silent Background Server**: Runs the heavy FastAPI backend seamlessly in the background with only the CLI interface visible to the user.

## Getting Started

### Prerequisites
- Python 3.9+
- Playwright (installed and configured via `playwright install`)
- A Google Cloud Project for OAuth and Gemini API access.

### 1. Configure Environment Variables (`.env`)
You must configure your API keys and local settings before running the server.

After running the installer (Step 3), your configuration files are stored securely in your user directory.
1. Open File Explorer and navigate to: `%USERPROFILE%\.sh4lu-z\Syntiox CORE\config` (e.g., `C:\Users\YourName\.sh4lu-z\Syntiox CORE\config`).
2. Copy `.env.example` and rename it to `.env`.
3. Open `.env` and configure your settings:
   - For Cloud LLM: Set `LLM_PROVIDER=google` and provide your `GEMINI_API_KEY`.
   - For Local LLM: Set `LLM_PROVIDER=local` and configure your `MODEL_PATH`.
   - Add other tool API keys as needed (Tavily, Firecrawl, etc.).

### 2. Configure Google Credentials (Google MCP)
If you want the agent to interact with Google Workspace (Drive, Gmail, Calendar, Docs, etc.), you must provide an OAuth Client ID from Google Cloud Console.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project and enable the necessary APIs (Gmail API, Drive API, Docs API, Calendar API).
3. Go to **APIs & Services > Credentials** and create an **OAuth 2.0 Client ID** (Desktop Application).
4. Download the JSON file and rename it to `credentials.json`.
5. Place this file inside your config directory: `%USERPROFILE%\.sh4lu-z\Syntiox CORE\config\credentials.json`.
6. Note: `credentials.example.json` is provided as a reference to verify the format.

### 3. Installation (Windows Only)
*Note: Currently, Syntiox CORE is supported on Windows environments only.*

Run the following PowerShell command to automatically install and configure Syntiox CORE:
```powershell
irm https://raw.githubusercontent.com/sh4lu-z/Syntiox-CORE/master/install.cmd -OutFile install.cmd ; .\install.cmd
```
The installer will set up your virtual environment, isolate configurations in your user profile, and expose the `stx` global command so you can run the AI from anywhere.

### 4. Running Syntiox CORE
Once installed, you can launch the system from anywhere using the `stx` command!

#### Standard Mode
```bash
stx
```
This connects to the existing background server and opens the interactive Textual CLI in your current terminal. If no server is running, it will temporarily start one attached to your terminal.

#### Persistent Background Mode (Recommended for Mobile/Remote)
```bash
stx --background
```
This launches the FastAPI backend silently in the background and **adds it to your Windows Startup folder** so it boots automatically when you turn on your PC. It will continue running even if you close the terminal.

#### Stop Background Server
```bash
stx --stop
```
This gracefully kills the persistent background server and removes it from the Windows Startup folder.

#### Debug Mode (Live Logs)
If you need to view the internal router logs, errors, or API requests:
```bash
stx --logs
```
If a background server is already running, this will stream live logs directly to your terminal. Otherwise, it will start a new server showing logs and spawn the CLI in a separate window.

#### Authentication Command
- `stx-google-login` : Run the Google OAuth setup process to authenticate the Google MCP. (Run this after placing your `credentials.json` in the config folder).

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
