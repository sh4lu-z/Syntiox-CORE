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

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/sh4lu-z/Syntiox-CORE.git
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your `.env` file (see `.env.example` if available).

### Usage
Start the background server:
```bash
python server.py
```
Or use the start script:
```bash
run.bat
```

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
