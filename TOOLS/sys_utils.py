import platform
import subprocess
import datetime
from TOOLS.logger import action_logger

@action_logger("get_system_info")
def get_system_info() -> str:
    """Returns basic system info including OS, CPU, RAM, and GPU."""
    info = []
    info.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    info.append(f"CPU: {platform.processor()}")
    
    try:
        ram_output = subprocess.check_output(
            ["powershell", "-Command", "Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum | Select-Object -ExpandProperty Sum"],
            text=True
        ).strip()
        if ram_output.isdigit():
            ram_gb = round(int(ram_output) / (1024**3))
            info.append(f"RAM: {ram_gb} GB")
        else:
            info.append(f"RAM: {ram_output}")
            
        gpu_output = subprocess.check_output(
            ["powershell", "-Command", "(Get-CimInstance Win32_VideoController).Name"],
            text=True
        ).strip()
        info.append(f"GPU: {gpu_output}")
        
        # Get live usage stats
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=0.5)
            ram_info = psutil.virtual_memory()
            info.append(f"CPU Usage: {cpu_usage}%")
            info.append(f"RAM Usage: {ram_info.percent}% ({round(ram_info.used / (1024**3), 2)}GB used / {round(ram_info.total / (1024**3), 2)}GB total)")
        except ImportError:
            # Fallback to PowerShell if psutil is not installed
            cpu_usage_out = subprocess.check_output(
                ["powershell", "-Command", "Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average | Select-Object -ExpandProperty Average"],
                text=True
            ).strip()
            info.append(f"CPU Usage: {cpu_usage_out}%")
            
            ram_free_out = subprocess.check_output(
                ["powershell", "-Command", "Get-WmiObject Win32_OperatingSystem | Select-Object -ExpandProperty FreePhysicalMemory"],
                text=True
            ).strip()
            ram_free_gb = round(int(ram_free_out) / (1024**2), 2)
            if 'ram_gb' in locals():
                used_ram = round(ram_gb - ram_free_gb, 2)
                percent = round((used_ram / ram_gb) * 100, 1)
                info.append(f"RAM Usage: {percent}% ({used_ram}GB used / {ram_gb}GB total)")
            else:
                info.append(f"Free RAM: {ram_free_gb} GB")
                
    except Exception as e:
        info.append(f"Hardware Info Error: {str(e)}")
        
    return "\n".join(info)

@action_logger("get_current_datetime")
def get_current_datetime() -> str:
    """Returns the exact current local time and date."""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

import threading

@action_logger("schedule")
def schedule(duration_seconds: int, prompt: str) -> str:
    """Schedules a timer to remind you about something after duration_seconds."""
    def reminder():
        msg = f"⏰ **[TIMER ALERT]** {prompt}"
        print(f"\n\n\033[93m{msg}\033[0m\n\n")
        try:
            import requests
            requests.post("http://127.0.0.1:8000/api/notify", json={"message": f"\n\n{msg}\n\n"})
            
            import backend.main as main_app
            main_app.chat_history.append(f"System: [TIMER ALERT] {prompt}")
        except Exception as e:
            print(f"Timer broadcast failed: {e}")

    t = threading.Timer(duration_seconds, reminder)
    t.daemon = True
    t.start()
    return f"Timer set for {duration_seconds} seconds. You will be reminded with: '{prompt}'"
