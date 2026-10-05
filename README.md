<p align="center">
  <img src="logo.svg" alt="Syntiox CORE Logo" width="300" />
</p>

<h1 align="center">Syntiox CORE</h1>

<p align="center">
  <strong>An Advanced Agentic AI OS running locally on your machine, powered by Google LLMs.</strong>
</p>

---

**Syntiox CORE** is an autonomous, on-demand Agentic AI system that dynamically routes user intents, leverages deep context memory, and controls complex subsystems—including a fully interactive browser subagent—to accomplish sophisticated, multi-step tasks on your behalf. 

Built exclusively around **Google's LLM ecosystem** (Gemini/Gemma), Syntiox CORE utilizes native Function Calling, Vision, and a highly optimized dynamic tool loader to manage over 100+ native integrations without exceeding token limits.

## ✨ Key Features

### 🧠 Dynamic Intent Routing & Tool Loading
Syntiox CORE is equipped with over **120+ tools** spanning system management, web search, and Google Workspace integrations. Instead of loading all tools simultaneously, a lightweight **Router LLM** evaluates user intent on the fly and dynamically loads only the specific tool packages (Skills) required for the task. This ensures maximum speed and optimal API token usage.

### 🌐 Autonomous Browser Subagent
Automates persistent web browsers natively using Playwright and CDP (Chrome DevTools Protocol). 
- Maintains active tabs, isolated sessions, and handles authentication cookies across reboots.
- Injects a beautiful custom UI overlay into the browser to display real-time agent logs and status directly over the web pages it controls.
- Can independently research, click, type, and extract information across multiple tabs.

### 🏢 Deep Google Workspace Integration
Natively reads, writes, and manages your digital life via an integrated Google MCP architecture:
- **Google Docs:** Create, edit, replace text, and extract data.
- **Google Drive:** Upload, download, manage permissions, and organize folders.
- **Google Forms:** Generate forms, add dynamic questions, and read responses.
- **Gmail & Calendar:** Read, send emails, organize labels, and manage events.

### 💾 Persistent Context Memory & "Brain" Projects
Maintains context across sessions for highly personalized responses. For massive, multi-day coding or research tasks, the agent utilizes the `create_project_brain` architecture to isolate memory into dedicated folders (e.g., maintaining `task.md` and `walkthrough.md`) to prevent hallucination over long execution loops.

### 🛡️ Enterprise-Grade Resilience
- **API Key Rotation:** Gracefully rotates between multiple `GEMINI_API_KEY`s to bypass rate limits (429/Quota Exhausted).
- **Self-Healing Execution:** The execution loop detects malformed API responses or hallucinated tools and automatically injects recovery prompts to stabilize the agent.
- **Secure Background Server:** Runs seamlessly as a FastAPI daemon in the background on Windows, exposing a highly responsive WebSocket and CLI interface.

---

## 🚀 Getting Started

### Prerequisites
- **Windows OS** (Syntiox CORE is heavily optimized for Windows environments).
- **Python 3.9+**
- **Playwright** (installed and configured via `playwright install`)
- A **Google Cloud Project** for OAuth (Workspace tools) and Gemini API access.

### 1. Installation

Run the following PowerShell command to automatically install and configure Syntiox CORE. This sets up your virtual environment, isolates configurations in your user profile, and exposes the global `stx` CLI command.

```powershell
irm https://raw.githubusercontent.com/sh4lu-z/Syntiox-CORE/master/install.cmd -OutFile install.cmd ; .\install.cmd
```

### 2. Configure Environment Variables (`.env`)

After installation, your configuration files are stored securely in your Windows user directory.

1. Navigate to: `%USERPROFILE%\.sh4lu-z\Syntiox CORE\config` 
2. Copy `.env.example` and rename it to `.env`.
3. Open `.env` and configure your settings:
   - Provide your `GEMINI_API_KEY` (You can comma-separate multiple keys for auto-rotation: `key1,key2`).
   - Configure the target model: `GOOGLE_MODEL=gemma-4-31b-it` (or your preferred Gemini model).

### 3. Configure Google Workspace Credentials (Optional)

If you want the agent to interact with your personal Google Drive, Gmail, Docs, etc., you must provide an OAuth Client ID from Google Cloud Console.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the APIs you need (Gmail, Drive, Docs, Forms, etc.).
3. Go to **APIs & Services > Credentials** and create an **OAuth 2.0 Client ID** (Desktop Application).
4. Download the JSON file, rename it to `credentials.json`, and place it in the config directory: `%USERPROFILE%\.sh4lu-z\Syntiox CORE\config\credentials.json`.
5. Run `stx-google-login` in your terminal to authenticate the agent.

### 4. Customizing Agent Behavior (SYNTIOX_CORE.md)

To give the agent custom rules, coding styles, or system-wide constraints, edit the `config/SYNTIOX_CORE.md` file. Any instructions placed in this markdown file are automatically injected into the agent's system prompt.

---

## 💻 Usage

Once installed, you can command your agent from anywhere using the `stx` global command!

### Standard CLI Mode
```bash
stx
```
Connects to the background server and opens the interactive CLI in your current terminal. If no server is running, it will temporarily start one attached to your terminal.

### Persistent Daemon Mode (Recommended)
```bash
stx --background
```
Launches the FastAPI backend silently in the background and **adds it to your Windows Startup folder** so the agent boots automatically when you turn on your PC. It will continue running even if you close the terminal.

### Stop Background Daemon
```bash
stx --stop
```
Gracefully kills the persistent background server and removes it from the Windows Startup folder.

### Update Syntiox CORE
```bash
stx --update
```
Automatically downloads and installs the latest version of Syntiox CORE from GitHub, keeping your agent and tools up to date.

### Debug Mode & Live Logs
```bash
stx --logs
```
Streams live internal router logs, API requests, and error traces directly to your terminal. If a background server is already running, this will attach to it; otherwise, it starts a new server.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
