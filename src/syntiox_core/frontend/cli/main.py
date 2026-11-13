import os
import sys
import re

# Ensure the root directory is in sys.path so 'backend' module is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import asyncio
import json
import websockets
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TextArea, Static, RichLog, OptionList, Input, Label, Button, Select, DirectoryTree
from textual.screen import ModalScreen
from textual.widgets.option_list import Option
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual import work
from textual.reactive import reactive
import dotenv
from textual.events import Key
from rich.markdown import Markdown
from rich.text import Text
from backend.session_manager import load_index

URI = 'ws://127.0.0.1:9999/ws'

class ChatInput(TextArea):
    def _on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            self.app.action_send_message()
        elif event.key == "shift+enter":
            event.prevent_default()
            self.insert("\n")

class HistoryScreen(ModalScreen[str]):
    BINDINGS = [("escape", "cancel", "Go Back")]

    def compose(self) -> ComposeResult:
        yield OptionList(id="history_list")

    def on_mount(self) -> None:
        index_data = load_index()
        option_list = self.query_one(OptionList)
        
        option_list.add_option(Option("❌ Cancel / Go Back", id="cancel"))
        
        if not index_data:
            option_list.add_option(Option("No chat history found.", id="none", disabled=True))
            return
            
        index_data.sort(key=lambda x: x["id"], reverse=True)
        for item in index_data:
            option_list.add_option(Option(f"[{item['id']}] {item['date']} - {item['title']}", id=str(item['id'])))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "cancel" or event.option.id == "none":
            self.dismiss(None)
        else:
            self.dismiss(event.option.id)
            
    def action_cancel(self):
        self.dismiss(None)

class ConfigScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Go Back")]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        home_dir = os.path.expanduser("~")
        data_dir = os.environ.get("SYNTIOX_DATA_DIR", os.path.join(home_dir, ".sh4lu-z", "Syntiox CORE"))
        self.config_dir = os.path.join(data_dir, "config")

        os.makedirs(os.path.join(self.config_dir, "local"), exist_ok=True)
        os.makedirs(os.path.join(self.config_dir, "examples"), exist_ok=True)

        self.env_file = os.path.join(self.config_dir, "local", ".env")

        
        if not os.path.exists(self.env_file):
            example = os.path.join(self.config_dir, "examples", ".env.example")

            if os.path.exists(example):
                import shutil
                shutil.copy(example, self.env_file)
        
        self.env_vars = dotenv.dotenv_values(self.env_file)
        self.inputs = {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="config_scroll"):
            yield Label("[bold #00CCFF]--- Syntiox CORE Configuration ---[/]")
            yield Label("Edit your .env settings below:")
            
            for key, val in self.env_vars.items():
                if key:
                    yield Label(f"[bold #FF00AA]{key}[/]")
                    if key == "LLM_PROVIDER":
                        options = [("google", "google")]
                        inp = Select(options, value="google", id=f"inp_{key}")
                    elif key == "VISION_ENABLED":
                        options = [("true", "true"), ("false", "false")]
                        inp = Select(options, value=str(val).lower() if val else "false", id=f"inp_{key}")
                    elif key == "THINKING_LEVEL":
                        cur_level = str(val).strip().upper() if val else "MEDIUM"
                        if cur_level not in ("MINIMAL", "LOW", "MEDIUM", "HIGH"):
                            cur_level = "MEDIUM"
                        options = [("MINIMAL", "MINIMAL"), ("LOW", "LOW"), ("MEDIUM", "MEDIUM"), ("HIGH", "HIGH")]
                        inp = Select(options, value=cur_level, id=f"inp_{key}")
                    else:
                        inp = Input(value=str(val) if val else "", id=f"inp_{key}")
                        
                    self.inputs[key] = inp
                    yield inp
                    
            yield Label("\n[bold #00CCFF]--- Google Credentials (MCP) ---[/]")
            cred_path = os.path.join(self.config_dir, "local", "credentials.json")

            if os.path.exists(cred_path):
                yield Label("✅ Status: [bold green]Credentials Installed[/]", id="lbl_cred_status")
                yield Button("🗑️ Delete Old Credentials & Tokens", id="btn_delete_cred", variant="error")
            else:
                yield Label("❌ Status: [bold red]Not Installed[/]", id="lbl_cred_status")
                
            guide = (
                "[dim]How to get credentials:\n"
                "1. Go to Google Cloud Console -> APIs & Services -> Credentials\n"
                "2. Create OAuth client ID (Desktop App)\n"
                "3. Download the JSON and paste the path below.[/dim]"
            )
            yield Label(guide)
            
            yield Label("Path to downloaded credentials.json:")
            self.cred_input = Input(placeholder="e.g. C:\\Downloads\\credentials.json", id="inp_cred")
            yield self.cred_input
            yield Button("Import Credentials", id="btn_import_cred", variant="primary")
            
            yield Label("\n[bold #00CCFF]--- Actions ---[/]")
            yield Button("Save & Restart Backend", id="btn_save", variant="success")
            yield Button("Cancel", id="btn_cancel", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_delete_cred":
            cred = os.path.join(self.config_dir, "local", "credentials.json")

            token = os.path.join(self.config_dir, "local", "token.json")

            if os.path.exists(cred): os.remove(cred)
            if os.path.exists(token): os.remove(token)
            
            try:
                self.query_one("#lbl_cred_status", Label).update("❌ Status: [bold red]Deleted[/]")
            except: pass
            
            self.notify("Credentials and Tokens deleted successfully!", title="Deleted", severity="warning")
            
        elif event.button.id == "btn_import_cred":
            path = self.cred_input.value.strip().strip('"').strip("'")
            if os.path.exists(path) and path.endswith('.json'):
                try:
                    import shutil
                    dest = os.path.join(self.config_dir, "local", "credentials.json")
                    shutil.copy(path, dest)
                    self.notify("Credentials imported successfully!", title="Success")
                    self.cred_input.value = ""
                except Exception as e:
                    self.notify(f"Error copying: {e}", title="Error", severity="error")
            else:
                self.notify("Invalid file path or not a JSON file.", title="Error", severity="error")
                
        elif event.button.id == "btn_save":
            for key, inp in self.inputs.items():
                # For Select widgets, value could be None/Select.BLANK if cleared
                val = str(inp.value) if inp.value is not None else ""
                if val == "Select.BLANK": val = ""
                dotenv.set_key(self.env_file, key, val)
            self.notify("Settings saved! Restarting...", title="Restarting")
            self.dismiss(True)

    def action_cancel(self):
        self.dismiss(False)

class ApprovalScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel"), ("y", "yes", "Yes"), ("n", "no", "No")]
    
    def __init__(self, tool: str = "", args: dict = None, risk: str = "", interaction_id: str = "", message: str = "", **kwargs):
        super().__init__(**kwargs)
        self.tool = tool
        self.args = args or {}
        self.risk = risk
        self.interaction_id = interaction_id
        self.message = message

    def compose(self) -> ComposeResult:
        if self.message:
            md_content = self.message
        else:
            args_str = json.dumps(self.args, indent=2, ensure_ascii=False)
            md_content = (
                f"| | |\n"
                f"|---|---|\n"
                f"| **Tool** | `{self.tool}` |\n"
                f"| **Risk** | {self.risk or 'This action may modify your system or files outside the scratch folder.'} |\n\n"
                f"**Arguments:**\n"
                f"```json\n{args_str}\n```"
            )
        with VerticalScroll(id="approval_scroll"):
            yield Label("[bold #FF0055]⚠️ ACTION APPROVAL REQUIRED[/]", id="approval_title")
            yield Static(Markdown(md_content), id="approval_text")
            yield Button("Yes (Execute)", id="btn_yes", variant="error")
            yield Button("No (Cancel)", id="btn_no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_yes":
            self.dismiss(True)
        elif event.button.id == "btn_no":
            self.dismiss(False)
            
    def action_cancel(self):
        self.dismiss(False)
        
    def action_yes(self):
        self.dismiss(True)
        
    def action_no(self):
        self.dismiss(False)

class McpPermissionScreen(ModalScreen[str]):
    BINDINGS = [("escape", "skip", "Skip")]

    def __init__(self, server: str = "", tool: str = "", args: dict = None, interaction_id: str = "", **kwargs):
        super().__init__(**kwargs)
        self.server = server
        self.tool = tool
        self.args = args or {}
        self.interaction_id = interaction_id

    def compose(self) -> ComposeResult:
        args_str = json.dumps(self.args, indent=2, ensure_ascii=False)
        md_content = (
            f"| | |\n"
            f"|---|---|\n"
            f"| **MCP Server** | `{self.server}` |\n"
            f"| **Tool** | `{self.tool}` |\n\n"
            f"**Arguments:**\n"
            f"```json\n{args_str}\n```"
        )
        with VerticalScroll(id="mcp_perm_scroll"):
            yield Label("[bold #FF0055]🔐 MCP TOOL PERMISSION[/]", id="mcp_perm_title")
            yield Static(Markdown(md_content), id="mcp_perm_text")
            yield Button("Run This Time", id="btn_run", variant="warning")
            yield Button("Allow Always", id="btn_allow", variant="success")
            yield Button("Skip", id="btn_skip", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_run":
            self.dismiss("run")
        elif event.button.id == "btn_allow":
            self.dismiss("allow_always")
        elif event.button.id == "btn_skip":
            self.dismiss("skip")

    def action_skip(self):
        self.dismiss("skip")

class QuestionScreen(ModalScreen[dict]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, question: str, interaction_id: str = "", options: list = None, is_multi_select: bool = False, allow_custom: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.question = question
        self.interaction_id = interaction_id
        self.options = options or []
        self.is_multi_select = is_multi_select
        self.allow_custom = allow_custom
        self.selected = set()

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="question_scroll"):
            yield Label("[bold #00CCFF]💬 Input Required[/]", id="question_title")
            yield Static(Markdown(self.question), id="question_text")
            if self.options:
                for i, opt in enumerate(self.options):
                    yield Button(f"  {opt}", id=f"opt_{i}", variant="default")
            if self.allow_custom or not self.options:
                yield Input(placeholder="Type your response...", id="custom_input")
            yield Button("Submit", id="btn_submit", variant="success")
            yield Button("Cancel", id="btn_cancel_q", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_submit":
            custom = ""
            try:
                custom = self.query_one("#custom_input", Input).value.strip()
            except Exception:
                pass
            self.dismiss({"selected": list(self.selected), "custom_text": custom})
        elif event.button.id == "btn_cancel_q":
            self.dismiss(None)
        elif event.button.id and event.button.id.startswith("opt_"):
            idx = int(event.button.id.split("_")[1])
            opt_val = self.options[idx]
            if self.is_multi_select:
                if opt_val in self.selected:
                    self.selected.discard(opt_val)
                    event.button.label = f"  {opt_val}"
                else:
                    self.selected.add(opt_val)
                    event.button.label = f"✓ {opt_val}"
            else:
                self.selected = {opt_val}
                for i, o in enumerate(self.options):
                    try:
                        btn = self.query_one(f"#opt_{i}", Button)
                        btn.label = f"✓ {o}" if o == opt_val else f"  {o}"
                    except Exception:
                        pass

    def action_cancel(self):
        self.dismiss(None)

class WorkspaceScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, current_workspace: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.current_workspace = current_workspace

    def compose(self) -> ComposeResult:
        current_label = self.current_workspace if self.current_workspace else "Scratch (No Workspace)"
        tree_root = os.path.expanduser("~")
        if self.current_workspace and os.path.isdir(self.current_workspace):
            parent = os.path.dirname(self.current_workspace)
            if parent and os.path.isdir(parent):
                tree_root = parent

        with VerticalScroll(id="workspace_scroll"):
            yield Label("[bold #00CCFF]📁 Open Workspace[/]", id="workspace_title")
            yield Label(f"Current: [bold white]{current_label}[/]", id="workspace_current")
            yield Input(
                value=self.current_workspace or "",
                placeholder="Enter folder path (e.g. F:\\MyProject) or pick below...",
                id="ws_path_input",
            )
            yield DirectoryTree(tree_root, id="workspace_tree")
            with Horizontal(id="workspace_actions"):
                yield Button("Open Workspace", id="btn_ws_open", variant="success")
                yield Button("Use Scratch Only", id="btn_ws_scratch", variant="warning")
                yield Button("Cancel", id="btn_ws_cancel", variant="default")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#ws_path_input", Input).value = str(event.path)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.query_one("#ws_path_input", Input).value = str(event.path.parent)

    def _submit_path(self) -> None:
        raw = self.query_one("#ws_path_input", Input).value.strip().strip('"').strip("'")
        if not raw:
            self.dismiss("")
            return
        abs_path = os.path.abspath(os.path.expanduser(raw))
        if not os.path.isdir(abs_path):
            self.notify(f"Folder not found: {abs_path}", title="Invalid Path", severity="error")
            return
        self.dismiss(abs_path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "ws_path_input":
            self._submit_path()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_ws_open":
            self._submit_path()
        elif event.button.id == "btn_ws_scratch":
            self.dismiss("")
        elif event.button.id == "btn_ws_cancel":
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

class ChatApp(App):
    CSS = """
    Screen {
        background: black;
    }
    #chat-container {
        height: 1fr;
        border: round #6600FF;
        background: black;
    }
    RichLog {
        height: 1fr;
        background: black;
    }
    #streaming-line {
        dock: bottom;
        height: auto;
        max-height: 8;
        padding-left: 1;
        color: #00CCFF;
    }
    ChatInput {
        height: 6;
        border: round #D500FF;
        background: black;
    }
    HistoryScreen {
        align: center middle;
    }
    #history_list {
        width: 80%;
        height: 70%;
        border: solid #FF00AA;
        background: black;
    }
    ConfigScreen {
        align: center middle;
    }
    #config_scroll {
        width: 80%;
        height: 80%;
        border: solid #00CCFF;
        background: black;
        padding: 1 2;
    }
    #config_scroll Label {
        margin-top: 1;
    }
    ApprovalScreen {
        align: center middle;
    }
    #approval_scroll {
        width: 70%;
        height: auto;
        max-height: 80%;
        border: thick red;
        background: black;
        padding: 1 2;
    }
    #approval_title {
        content-align: center middle;
        width: 100%;
        margin-bottom: 1;
    }
    #approval_scroll Button {
        width: 100%;
        margin-top: 1;
    }
    QuestionScreen {
        align: center middle;
    }
    #question_scroll {
        width: 70%;
        height: auto;
        max-height: 80%;
        border: thick #00CCFF;
        background: black;
        padding: 1 2;
    }
    #question_title {
        content-align: center middle;
        width: 100%;
        margin-bottom: 1;
    }
    #question_scroll Button {
        width: 100%;
        margin-top: 1;
    }
    #question_scroll Input {
        margin-top: 1;
    }
    McpPermissionScreen {
        align: center middle;
    }
    #mcp_perm_scroll {
        width: 70%;
        height: auto;
        max-height: 80%;
        border: thick #D500FF;
        background: black;
        padding: 1 2;
    }
    #mcp_perm_title {
        content-align: center middle;
        width: 100%;
        margin-bottom: 1;
    }
    #mcp_perm_scroll Button {
        width: 100%;
        margin-top: 1;
    }
    #workspace-bar {
        height: auto;
        background: #0d0d14;
        padding: 0 1;
    }
    #btn_workspace {
        height: 1;
        border: none;
        background: #181828;
        color: #00CCFF;
        padding: 0 2;
    }
    WorkspaceScreen {
        align: center middle;
    }
    #workspace_scroll {
        width: 80%;
        height: 80%;
        border: thick #00CCFF;
        background: black;
        padding: 1 2;
    }
    #workspace_title {
        content-align: center middle;
        width: 100%;
        margin-bottom: 1;
    }
    #workspace_current {
        margin-bottom: 1;
    }
    #workspace_tree {
        height: 1fr;
        min-height: 12;
        border: round #6600FF;
        margin-top: 1;
        margin-bottom: 1;
    }
    #workspace_actions {
        height: auto;
        width: 100%;
    }
    #workspace_actions Button {
        width: 1fr;
        margin-right: 1;
    }
    """
    BINDINGS = [
        ("ctrl+s", "send_message", "Send Message"),
        ("ctrl+o", "open_workspace", "Workspace"),
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+x", "toggle_mode", "Toggle Mode"),
        ("ctrl+y", "copy_code", "Copy Code")
    ]
    
    current_mode = reactive("auto")
    current_state_msg = reactive("")
    current_workspace = None
    spinner_idx = 0
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def compose(self) -> ComposeResult:
        yield Header(icon="💠")
        with Horizontal(id="workspace-bar"):
            yield Button("📁 Workspace: Scratch", id="btn_workspace")
        with Vertical(id="chat-container"):
            self.log_view = RichLog(highlight=True, markup=True, wrap=True)
            yield self.log_view
            self.stream_view = Static(id="streaming-line")
            yield self.stream_view
        self.input_area = ChatInput(language="markdown", show_line_numbers=False)
        yield self.input_area
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Syntiox CORE - Chat Interface"
        self.sub_title = "Mode: AUTO | Workspace: Scratch"
        self.websocket = None
        self.ws_loop = None
        self.copy_index = 0
        self.thinking_buffers = {}
        self._streaming_ai = False
        logo = """[#FF0055]     ▄▄████▄▄     [/]
[#FF00AA]   ▄██████████▄   [/]
[#D500FF] ▄██████████████▄ [/]
[#6600FF] ▀██████████████▀ [/]
[#0055FF]   ▀██████████▀   [/]
[#00CCFF]     ▀▀████▀▀     [/]"""
        
        info_text = f"""
[bold white]Syntiox CORE 1.0.0[/]
[dim]~[/dim]"""
        from rich.table import Table
        from rich.text import Text
        
        table = Table.grid(padding=(0, 3))
        table.add_column()
        table.add_column()
        table.add_row(Text.from_markup(logo), Text.from_markup(info_text))
        
        self.log_view.write(table)
        self.log_view.write("")
        help_text = """
[dim]Type your message or say 'Hey Syntiox' to speak.
Type '/help' to see all available commands and shortcuts.[/dim]
"""
        self.log_view.write(Text.from_markup(help_text))
        
        self.set_interval(0.1, self.tick_spinner)
        self.run_websocket()
        # self.load_tts_model()

    # @work(thread=True)
    # def load_tts_model(self) -> None:
    #     try:
    #         import pygame
    #         pygame.mixer.init()
    #         self.call_from_thread(self.add_system_message, "--- High Quality AI Voice (Edge TTS) Loaded ---")
    #     except Exception as e:
    #         self.call_from_thread(self.add_system_message, f"--- AI Voice Load Error: {e} ---")

    def _render_stream_view(self):
        out = Text()
        if self.current_state_msg:
            char = self.spinner_chars[self.spinner_idx]
            out.append(f"{char} {self.current_state_msg}...", style="bold yellow")
        thinking_buffers = getattr(self, "thinking_buffers", {})
        active_id = None
        live_think = ""
        if thinking_buffers.get("main"):
            active_id = "main"
            live_think = thinking_buffers["main"]
        else:
            for aid, buf in thinking_buffers.items():
                if buf:
                    active_id = aid
                    live_think = buf
                    break
        if live_think:
            tail_lines = [ln for ln in live_think.splitlines() if ln.strip()][-4:]
            tail_preview = "\n".join(tail_lines)
            if len(tail_preview) > 360:
                tail_preview = "..." + tail_preview[-357:]
            if tail_preview:
                if len(out):
                    out.append("\n")
                prefix = f"[{active_id}] " if active_id and active_id != "main" else ""
                out.append(f"{prefix}💭 {tail_preview}", style="dim italic #A78BFA")
        elif not len(out) and getattr(self, "_streaming_ai", False):
            out.append("Syntiox CORE: ", style="bold #D500FF")
        self.stream_view.update(out if len(out) else "")

    def tick_spinner(self):
        if self.current_state_msg:
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            self._render_stream_view()

    def watch_current_mode(self, mode: str):
        self.sub_title = f"Mode: {mode.upper()}"

    def add_system_message(self, text: str):
        self.log_view.write(f"[bold #00CCFF]{text}[/]")

    def add_user_message(self, text: str):
        self.log_view.write(f"[bold #FF00AA]You:[/] {text}\n")

    def append_thinking_message(self, text: str, agent_id: str = "main"):
        if not text:
            return
        if not hasattr(self, "thinking_buffers"):
            self.thinking_buffers = {}
        self.thinking_buffers[agent_id] = self.thinking_buffers.get(agent_id, "") + text
        if agent_id == "main" and not self.current_state_msg:
            self.current_state_msg = "Thinking"
        self._render_stream_view()

    def flush_thinking_message(self, agent_id: str = "main"):
        if not hasattr(self, "thinking_buffers"):
            return
        raw_thought = self.thinking_buffers.pop(agent_id, "").strip()
        if raw_thought:
            label = f"🤖 [{agent_id}] 💭 Thinking\n" if agent_id != "main" else "💭 Thinking\n"
            t = Text()
            t.append(label, style="bold #A78BFA")
            t.append(raw_thought, style="dim italic #9CA3AF")
            self.log_view.write(t)
        self._render_stream_view()

    def start_ai_message(self):
        self.current_ai_buffer = ""
        self.final_msg_buffer = ""
        self.copy_index = 0
        self._streaming_ai = True
        self._render_stream_view()

    def append_ai_message(self, text: str):
        self.current_ai_buffer += text

    def overwrite_ai_message(self, text: str):
        self.current_ai_buffer = text

    def finalize_ai_message(self):
        self._streaming_ai = False
        self._render_stream_view()
        
        import re
        clean_msg = self.current_ai_buffer
        clean_msg = re.sub(r'<SCRATCHPAD>.*?</SCRATCHPAD>', '', clean_msg, flags=re.DOTALL | re.IGNORECASE)
        clean_msg = re.sub(r"<task_complete\s*/>", "", clean_msg, flags=re.IGNORECASE)
        clean_msg = re.sub(r"<next_step_required\s*/>", "", clean_msg, flags=re.IGNORECASE)
        self.current_ai_buffer = clean_msg.strip()
        
        self.log_view.write(Markdown(f"**Syntiox CORE:** {self.current_ai_buffer}"))
        self.log_view.write("") # Add spacing
        
        # Audio playback using Kokoro or fallback to PowerShell
        # import re, threading
        # 
        # def _speak():
        #     clean = re.sub(r'[*_#`]', '', self.current_ai_buffer)
        #     clean = clean.replace("'", "").replace('"', "").replace("\n", " ")
        #     
        #     try:
        #         import asyncio
        #         import edge_tts
        #         import pygame
        #         import tempfile
        #         
        #         if pygame.mixer.get_init():
        #             pygame.mixer.music.stop()
        #             try: pygame.mixer.music.unload()
        #             except Exception: pass
        #             
        #         async def _gen_and_play():
        #             voice = "en-US-ChristopherNeural"
        #             temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        #             temp_path = temp_file.name
        #             temp_file.close()
        #             communicate = edge_tts.Communicate(clean, voice)
        #             await communicate.save(temp_path)
        #             
        #             if not pygame.mixer.get_init():
        #                 pygame.mixer.init()
        #             pygame.mixer.music.load(temp_path)
        #             pygame.mixer.music.play()
        #             # Wait for playback then cleanup
        #             while pygame.mixer.music.get_busy():
        #                 await asyncio.sleep(0.5)
        #             pygame.mixer.music.unload()
        #             try:
        #                 os.remove(temp_path)
        #             except Exception:
        #                 pass
        #             
        #         asyncio.run(_gen_and_play())
        #     except Exception as e:
        #         self.call_from_thread(self.add_system_message, f"[Voice Error] {e}")
        #     
        # threading.Thread(target=_speak, daemon=True).start()

    @work(exclusive=True, thread=True)
    def run_websocket(self) -> None:
        self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)
        self.ws_loop.run_until_complete(self.websocket_loop())

    def _send_ws_payload(self, payload: dict) -> bool:
        ws = getattr(self, "websocket", None)
        ws_loop = getattr(self, "ws_loop", None)
        ws_state = getattr(ws, "state", None) if ws is not None else None
        if not ws or not ws_loop or (ws_state is not None and getattr(ws_state, "name", str(ws_state)).upper() != "OPEN"):
            self.add_system_message("Not connected to server. Please wait for reconnection.")
            return False
        try:
            fut = asyncio.run_coroutine_threadsafe(ws.send(json.dumps(payload, ensure_ascii=False)), ws_loop)

            def _on_send_done(f):
                try:
                    f.result()
                except Exception as err:
                    try:
                        self.call_from_thread(self.add_system_message, f"Failed to send message: {err}")
                    except Exception:
                        pass

            fut.add_done_callback(_on_send_done)
            return True
        except Exception as e:
            self.add_system_message(f"Failed to send message: {e}")
            return False

    def _reset_ui_on_disconnect(self):
        self.thinking_buffers = {}
        self._streaming_ai = False
        if isinstance(self.screen, (ApprovalScreen, QuestionScreen, McpPermissionScreen)):
            try:
                self.pop_screen()
            except Exception:
                pass
        self.update_state("Idle")

    async def websocket_loop(self):
        while True:
            pending_thinking = set()
            try:
                async with websockets.connect(URI, ping_interval=20, ping_timeout=60) as ws:
                    self.websocket = ws
                    self.call_from_thread(self.add_system_message, "--- Connected to Server ---")
                    if self.current_workspace:
                        await ws.send(json.dumps({"action": "set_workspace", "path": self.current_workspace}))
                    else:
                        await ws.send(json.dumps({"action": "get_workspace"}))
                    
                    is_new_message = True
                    
                    while True:
                        try:
                            raw_text = await ws.recv()
                            try:
                                payload = json.loads(raw_text)
                            except json.JSONDecodeError:
                                continue

                            event_type = payload.get("event")
                            agent_id = payload.get("agent_id", "main")
                            prefix = f"🤖 [{agent_id}] " if agent_id != "main" else ""

                            if event_type == "state":
                                status_msg = payload.get("status", "Thinking")
                                if agent_id == "main":
                                    self.call_from_thread(self.update_state, status_msg)
                                else:
                                    self.call_from_thread(self.add_system_message, f"{prefix}Status: {status_msg}")

                            elif event_type == "thinking":
                                think_chunk = payload.get("data", "")
                                if think_chunk:
                                    pending_thinking.add(agent_id)
                                    self.call_from_thread(self.append_thinking_message, think_chunk, agent_id)

                            elif event_type == "token":
                                if agent_id in pending_thinking:
                                    pending_thinking.discard(agent_id)
                                    self.call_from_thread(self.flush_thinking_message, agent_id)
                                token_str = payload.get("data", "")
                                token_str = re.sub(r"<next_step_required\s*/>", "", token_str)
                                token_str = re.sub(r"<task_complete\s*/>", "", token_str)
                                if token_str:
                                    if is_new_message:
                                        self.call_from_thread(self.start_ai_message)
                                        is_new_message = False
                                    self.call_from_thread(self.append_ai_message, token_str)

                            elif event_type == "tool_call":
                                if agent_id in pending_thinking:
                                    pending_thinking.discard(agent_id)
                                    self.call_from_thread(self.flush_thinking_message, agent_id)
                                tool_name = payload.get("tool", "unknown")
                                tool_args = payload.get("args", {})
                                args_summary = ", ".join(f"{k}={repr(v)[:40]}" for k, v in tool_args.items())
                                msg = f"{prefix}🔧 Tool Call: {tool_name}({args_summary})" if args_summary else f"{prefix}🔧 Tool Call: {tool_name}"
                                self.call_from_thread(self.add_system_message, msg)

                            elif event_type == "tool_result":
                                tool_name = payload.get("tool", "unknown")
                                output_str = str(payload.get("output", "")).strip()
                                preview = (output_str[:120] + "...") if len(output_str) > 120 else output_str
                                msg = f"{prefix}✔ Tool Result ({tool_name}): {preview}" if preview else f"{prefix}✔ Tool Result ({tool_name})"
                                self.call_from_thread(self.add_system_message, msg)

                            elif event_type == "interaction_required":
                                if agent_id in pending_thinking:
                                    pending_thinking.discard(agent_id)
                                    self.call_from_thread(self.flush_thinking_message, agent_id)
                                iid = payload.get("interaction_id", "")
                                itype = payload.get("interaction_type", "")
                                ipayload = payload.get("payload", {})
                                prompt_md = payload.get("prompt", "")

                                if itype == "approval":
                                    tool_name = ipayload.get("tool", "")
                                    tool_args = ipayload.get("args", {})
                                    tool_risk = ipayload.get("risk", "")

                                    def handle_approval(approved, _iid=iid):
                                        if not self.websocket or not self.ws_loop:
                                            return
                                        if approved is None:
                                            approved = False
                                        sent = self._send_ws_payload({
                                            "action": "interaction_response",
                                            "interaction_id": _iid,
                                            "approved": approved,
                                        })
                                        if sent:
                                            self.add_user_message("Approved" if approved else "Denied")
                                            self.update_state("Resuming" if approved else "Denied")
                                    self.call_from_thread(self.push_screen, ApprovalScreen(tool=tool_name, args=tool_args, risk=tool_risk, interaction_id=iid, message=prompt_md), handle_approval)
                                    self.call_from_thread(self.update_state, "Awaiting Approval")
                                    is_new_message = True

                                elif itype == "question":
                                    q_text = ipayload.get("question", prompt_md or "Input required")
                                    q_options = ipayload.get("options")
                                    q_multi = ipayload.get("is_multi_select", False)
                                    q_custom = ipayload.get("allow_custom", True)

                                    def handle_question(result, _iid=iid):
                                        if not self.websocket or not self.ws_loop:
                                            return
                                        if result is None:
                                            body = {
                                                "action": "interaction_response",
                                                "interaction_id": _iid,
                                                "custom_text": "[cancelled]",
                                            }
                                            answer = "[cancelled]"
                                        else:
                                            body = {
                                                "action": "interaction_response",
                                                "interaction_id": _iid,
                                                "selected": result.get("selected", []),
                                                "custom_text": result.get("custom_text", ""),
                                            }
                                            selected = result.get("selected") or []
                                            custom = result.get("custom_text", "")
                                            if selected:
                                                answer = ", ".join(selected) + (f" ({custom})" if custom else "")
                                            else:
                                                answer = custom or "[cancelled]"
                                        if self._send_ws_payload(body):
                                            self.add_user_message(answer)
                                            self.update_state("Resuming")
                                    self.call_from_thread(self.push_screen, QuestionScreen(q_text, interaction_id=iid, options=q_options, is_multi_select=q_multi, allow_custom=q_custom), handle_question)
                                    self.call_from_thread(self.update_state, "Awaiting Input")
                                    is_new_message = True

                                elif itype == "mcp_permission":
                                    mcp_server = ipayload.get("server", "")
                                    mcp_tool = ipayload.get("tool", "")
                                    mcp_args = ipayload.get("args", {})

                                    def handle_mcp_perm(decision, _iid=iid):
                                        if not self.websocket or not self.ws_loop:
                                            return
                                        if decision is None:
                                            decision = "skip"
                                        sent = self._send_ws_payload({
                                            "action": "interaction_response",
                                            "interaction_id": _iid,
                                            "decision": decision,
                                        })
                                        if sent:
                                            self.add_user_message(f"MCP Permission: {decision}")
                                            self.update_state("Resuming")
                                    self.call_from_thread(self.push_screen, McpPermissionScreen(server=mcp_server, tool=mcp_tool, args=mcp_args, interaction_id=iid), handle_mcp_perm)
                                    self.call_from_thread(self.update_state, "Awaiting MCP Permission")
                                    is_new_message = True

                            elif event_type == "system":
                                sys_msg = payload.get("message", "")
                                if sys_msg:
                                    self.call_from_thread(self.add_system_message, sys_msg)

                            elif event_type == "workspace_changed":
                                self.call_from_thread(self.update_workspace_ui, payload)

                            elif event_type == "final":
                                for aid in list(pending_thinking):
                                    self.call_from_thread(self.flush_thinking_message, aid)
                                pending_thinking.clear()
                                final_content = payload.get("content", "").strip()
                                if is_new_message:
                                    self.call_from_thread(self.start_ai_message)
                                self.call_from_thread(self.overwrite_ai_message, final_content)
                                self.call_from_thread(self.finalize_ai_message)
                                self.call_from_thread(self.update_state, "Idle")
                                is_new_message = True
                                
                        except websockets.exceptions.ConnectionClosed:
                            self.websocket = None
                            pending_thinking.clear()
                            self.call_from_thread(self._reset_ui_on_disconnect)
                            self.call_from_thread(self.add_system_message, "--- Connection lost ---")
                            break
            except ConnectionRefusedError:
                self.websocket = None
                self.call_from_thread(self.add_system_message, "Cannot connect. Retrying...")
                await asyncio.sleep(3)
            except Exception as e:
                self.websocket = None
                self.call_from_thread(self._reset_ui_on_disconnect)
                self.call_from_thread(self.add_system_message, f"Error: {e}")
                await asyncio.sleep(3)
            finally:
                self.websocket = None

    def update_state(self, state: str):
        if state.lower() == "idle":
            self.current_state_msg = ""
            self._render_stream_view()
        else:
            self.current_state_msg = state
            self._render_stream_view()

    def _refresh_subtitle(self):
        ws_name = os.path.basename(self.current_workspace) or self.current_workspace if self.current_workspace else "Scratch"
        self.sub_title = f"Mode: {self.current_mode.upper()} | Workspace: {ws_name}"

    def update_workspace_ui(self, payload: dict):
        new_ws = payload.get("workspace")
        changed = (new_ws != self.current_workspace)
        self.current_workspace = new_ws
        ws_name = os.path.basename(new_ws) or new_ws if new_ws else "Scratch"
        try:
            self.query_one("#btn_workspace", Button).label = f"📁 Workspace: {ws_name}"
        except Exception:
            pass
        self._refresh_subtitle()
        if changed:
            if new_ws:
                self.add_system_message(f"--- Workspace set to: {new_ws} ---")
            else:
                self.add_system_message("--- Workspace cleared (using Scratch) ---")

    def send_set_workspace(self, ws_path: str | None):
        clean_path = ws_path.strip() if isinstance(ws_path, str) and ws_path.strip() else None
        self.current_workspace = clean_path
        if self.websocket and self.ws_loop:
            payload = json.dumps({"action": "set_workspace", "path": clean_path})
            asyncio.run_coroutine_threadsafe(self.websocket.send(payload), self.ws_loop)
        else:
            self.update_workspace_ui({"workspace": clean_path})

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_workspace":
            self.action_open_workspace()

    def action_open_workspace(self):
        def handle_workspace_result(result: str | None):
            if result is None:
                return
            self.send_set_workspace(result or None)
        self.push_screen(WorkspaceScreen(current_workspace=self.current_workspace), handle_workspace_result)

    def action_send_message(self):
        text = self.input_area.text.strip()
        if not text: return
        
        # Check commands
        if text.lower() == "/config":
            self.input_area.text = ""
            def check_config_result(restart: bool | None):
                if restart:
                    sys.exit(42)
            self.push_screen(ConfigScreen(), check_config_result)
            return

        if text.lower() == "/workspace" or text.lower().startswith("/workspace "):
            arg = text[len("/workspace"):].strip()
            self.input_area.text = ""
            if not arg:
                self.action_open_workspace()
            elif arg.lower() in ("clear", "none", "scratch"):
                self.send_set_workspace(None)
            else:
                abs_path = os.path.abspath(os.path.expanduser(arg.strip('"').strip("'")))
                if os.path.isdir(abs_path):
                    self.send_set_workspace(abs_path)
                else:
                    self.add_system_message(f"Invalid workspace directory: {abs_path}")
            return

        if text.lower() == "/help":
            self.input_area.text = ""
            help_msg = """
---
**Syntiox CORE Commands & Shortcuts**

*   **/workspace [path|clear]** - Open or clear project workspace (`Ctrl+O`)
*   **/config** - Open Settings UI (API Keys, LLM Provider, etc.)
*   **/history** - View and load past chat sessions
*   **/new** - Start a fresh new session
*   **/mode <mode>** - Change AI mode (`auto`, `chat`, `agent`)
*   **/help** - Show this help menu

**Keyboard Shortcuts:**
*   **Ctrl+S** or **Enter** - Send message
*   **Ctrl+O** - Open Workspace picker
*   **Shift+Enter** - New line in chat input
*   **Ctrl+X** - Quick toggle mode (Auto -> Chat -> Agent)
*   **Ctrl+Y** - Copy last generated code block
*   **Ctrl+C** - Quit Application
---
"""
            self.log_view.write(Markdown(help_msg))
            return

        if text.lower() == "/history":
            self.input_area.text = ""
            def check_history_result(session_id: str | None):
                if session_id:
                    self.add_system_message(f"--- Loading session {session_id} ---")
                    self._send_ws_payload({"command": f"/load {session_id}", "mode": self.current_mode})
            self.push_screen(HistoryScreen(), check_history_result)
            return

        if text.lower() in ["/new"] or text.lower().startswith("/load ") or text.lower().startswith("/mode "):
            if text.lower().startswith("/mode "):
                mode = text.lower().replace("/mode ", "").strip()
                if mode in ["auto", "chat", "agent"]:
                    self.current_mode = mode
                    self._refresh_subtitle()
                    self.add_system_message(f"--- Mode switched to {mode.upper()} ---")
            self.input_area.text = ""
            if text.lower().startswith("/mode "): return
            # /new and /load should be sent to backend, not displayed as user message
            self._send_ws_payload({"command": text, "mode": self.current_mode})
            return
                
        self.add_user_message(text)
        self.input_area.text = ""
        
        self._send_ws_payload({"command": text, "mode": self.current_mode})

    def action_toggle_mode(self):
        modes = ["auto", "chat", "agent"]
        try:
            idx = modes.index(self.current_mode)
        except ValueError:
            idx = 0
        self.current_mode = modes[(idx + 1) % len(modes)]
        self._refresh_subtitle()
        self.add_system_message(f"--- Mode switched to {self.current_mode.upper()} ---")

    def action_copy_code(self) -> None:
        import re
        if not hasattr(self, "current_ai_buffer") or not self.current_ai_buffer:
            self.notify("No message to copy from.", title="Error", severity="error")
            return
            
        matches = list(re.finditer(r'```([a-zA-Z]*)\n(.*?)\n```', self.current_ai_buffer, flags=re.DOTALL))
        if matches:
            idx = getattr(self, "copy_index", 0) % len(matches)
            match = matches[idx]
            lang = match.group(1).upper() if match.group(1) else "Code"
            code_text = match.group(2).strip()
            
            try:
                self.copy_to_clipboard(code_text)
                self.notify(f"Copied {lang} block ({idx + 1}/{len(matches)})", title="Success", severity="information")
                self.copy_index = idx + 1
            except Exception as e:
                self.notify(f"Failed to copy: {e}", title="Error", severity="error")
        else:
            self.notify("No code block found in the last message.", title="Error", severity="error")

if __name__ == "__main__":
    app = ChatApp()
    app.run()
