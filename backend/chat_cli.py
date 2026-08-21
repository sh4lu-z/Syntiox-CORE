import os
import sys

# Ensure the root directory is in sys.path so 'backend' module is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import websockets
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TextArea, Static, RichLog, OptionList
from textual.screen import ModalScreen
from textual.widgets.option_list import Option
from textual.containers import Vertical
from textual import work
from textual.reactive import reactive
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
    """
    BINDINGS = [
        ("ctrl+s", "send_message", "Send Message"),
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+x", "toggle_mode", "Toggle Mode"),
        ("ctrl+y", "copy_code", "Copy Code")
    ]
    
    current_mode = reactive("auto")
    current_state_msg = reactive("")
    spinner_idx = 0
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def compose(self) -> ComposeResult:
        yield Header(icon="💠")
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
        self.sub_title = "Mode: AUTO"
        self.websocket = None
        self.ws_loop = None
        self.copy_index = 0
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
Mode Toggle: '/mode auto', '/mode chat', '/mode agent'
Sessions   : '/history', '/load <id>', '/new'

(Use Ctrl+S or Enter to send. Shift+Enter for new line. Ctrl+X to toggle mode. Ctrl+Y to copy code.)[/dim]
"""
        self.log_view.write(Text.from_markup(help_text))
        
        self.set_interval(0.1, self.tick_spinner)
        self.run_websocket()

    def tick_spinner(self):
        if self.current_state_msg:
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            char = self.spinner_chars[self.spinner_idx]
            self.stream_view.update(f"[bold yellow]{char} {self.current_state_msg}...[/bold yellow]")

    def watch_current_mode(self, mode: str):
        self.sub_title = f"Mode: {mode.upper()}"

    def add_system_message(self, text: str):
        self.log_view.write(f"[bold #00CCFF]{text}[/]")

    def add_user_message(self, text: str):
        self.log_view.write(f"[bold #FF00AA]You:[/] {text}\n")

    def start_ai_message(self):
        self.current_ai_buffer = ""
        self.final_msg_buffer = ""
        self.copy_index = 0
        self.stream_view.update("[bold #D500FF]Syntiox CORE:[/] ")

    def append_ai_message(self, text: str):
        self.current_ai_buffer += text

    def overwrite_ai_message(self, text: str):
        self.current_ai_buffer = text

    def finalize_ai_message(self):
        self.stream_view.update("")
        self.log_view.write(Markdown(f"**Syntiox CORE:** {self.current_ai_buffer}"))
        self.log_view.write("") # Add spacing

    @work(exclusive=True, thread=True)
    def run_websocket(self) -> None:
        self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)
        self.ws_loop.run_until_complete(self.websocket_loop())

    async def websocket_loop(self):
        while True:
            try:
                async with websockets.connect(URI) as ws:
                    self.websocket = ws
                    self.call_from_thread(self.add_system_message, "--- Connected to Server ---")
                    
                    receiving_final = False
                    is_new_message = True
                    
                    while True:
                        try:
                            text = await ws.recv()
                            
                            while "[STATE:" in text:
                                start_idx = text.find("[STATE:")
                                end_idx = text.find("]", start_idx)
                                if end_idx != -1:
                                    state_str = text[start_idx:end_idx+1]
                                    state_name = state_str.replace("[STATE:", "").replace("]", "")
                                    self.call_from_thread(self.update_state, state_name)
                                    text = text.replace(state_str, "")
                                else:
                                    break
                                    
                            while "[TOOL_UI:" in text:
                                start = text.find("[TOOL_UI:")
                                end = text.find("]", start)
                                if end != -1:
                                    tool_str = text[start:end+1]
                                    # We don't display the tool usage to the user anymore
                                    # tool_name = tool_str.replace("[TOOL_UI:", "").replace("]", "")
                                    # self.call_from_thread(self.add_system_message, f"🔧 Used Tool: {tool_name}")
                                    text = text.replace(tool_str, "")
                                else:
                                    break
                                    
                            if "[NEXT_STEP_REQUIRED]" in text:
                                text = text.replace("[NEXT_STEP_REQUIRED]", "")
                                
                            if "[TASK_COMPLETE]" in text:
                                text = text.replace("[TASK_COMPLETE]", "")

                            if "[__SYNTIOX_FINAL__]" in text:
                                receiving_final = True
                                text = text.split("[__SYNTIOX_FINAL__]")[1]
                                self.final_msg_buffer = ""
                                
                            if receiving_final:
                                if "[__SYNTIOX_DONE__]" in text:
                                    receiving_final = False
                                    text = text.replace("[__SYNTIOX_DONE__]", "")
                                    self.final_msg_buffer += text
                                    
                                    # Overwrite the buffer with the final cleaned message to avoid duplication
                                    self.call_from_thread(self.overwrite_ai_message, self.final_msg_buffer.strip())
                                    self.call_from_thread(self.finalize_ai_message)
                                    self.call_from_thread(self.update_state, "Idle")
                                    is_new_message = True
                                    continue
                                else:
                                    self.final_msg_buffer += text
                                    continue
                                    
                            if text:
                                if is_new_message:
                                    self.call_from_thread(self.start_ai_message)
                                    is_new_message = False
                                self.call_from_thread(self.append_ai_message, text)
                                
                        except websockets.exceptions.ConnectionClosed:
                            self.call_from_thread(self.add_system_message, "--- Connection lost ---")
                            break
            except ConnectionRefusedError:
                self.call_from_thread(self.add_system_message, "Cannot connect. Retrying...")
                await asyncio.sleep(3)
            except Exception as e:
                self.call_from_thread(self.add_system_message, f"Error: {e}")
                await asyncio.sleep(3)

    def update_state(self, state: str):
        if state.lower() == "idle":
            self.current_state_msg = ""
            self.stream_view.update("")
        else:
            self.current_state_msg = state

    def action_send_message(self):
        text = self.input_area.text.strip()
        if not text: return
        
        # Check commands
        if text.lower() == "/history":
            self.input_area.text = ""
            def check_history_result(session_id: str | None):
                if session_id:
                    self.add_system_message(f"--- Loading session {session_id} ---")
                    payload = json.dumps({"command": f"/load {session_id}", "mode": self.current_mode})
                    asyncio.run_coroutine_threadsafe(self.websocket.send(payload), self.ws_loop)
            self.push_screen(HistoryScreen(), check_history_result)
            return

        if text.lower() in ["/new"] or text.lower().startswith("/load ") or text.lower().startswith("/mode "):
            if text.lower().startswith("/mode "):
                mode = text.lower().replace("/mode ", "").strip()
                if mode in ["auto", "chat", "agent"]:
                    self.current_mode = mode
                    self.add_system_message(f"--- Mode switched to {mode.upper()} ---")
            self.input_area.text = ""
            if text.lower().startswith("/mode "): return
                
        self.add_user_message(text)
        self.input_area.text = ""
        
        if self.websocket and self.ws_loop:
            payload = json.dumps({"command": text, "mode": self.current_mode})
            asyncio.run_coroutine_threadsafe(self.websocket.send(payload), self.ws_loop)

    def action_toggle_mode(self):
        modes = ["auto", "chat", "agent"]
        idx = modes.index(self.current_mode)
        self.current_mode = modes[(idx + 1) % len(modes)]
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
