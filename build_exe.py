import os
import sys
import subprocess

def build_exe():
    print("Starting Syntiox CORE Executable Build Process...")
    
    # Base command
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "Syntiox_CORE",
    ]
    
    if os.path.exists("logo.ico"):
        cmd.extend(["--icon", "logo.ico"])
        
    # --- MICRO-CORE: EXCLUDE HEAVY MODULES ---
    heavy_modules = [
        "uvicorn", "playwright", "llama_cpp", "fastapi", 
        "websockets", "textual", "rich", "torch", "numpy", "pandas"
    ]
    for mod in heavy_modules:
        cmd.extend(["--exclude-module", mod])
    # -----------------------------------------
        
    # Folders that need to be included inside the exe
    # Syntax for windows is "source;destination"
    folders_to_include = [
        "backend",
        "frontend",
        "config",
        "MCP",
        "SKILLS",
        "TOOLS"
    ]
    
    for folder in folders_to_include:
        if os.path.exists(folder):
            cmd.extend(["--add-data", f"{folder};{folder}"])
            
    # Include requirements and other necessary files if any
    files_to_include = [
        "requirements.txt",
        ".gitignore",
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "LICENSE"
    ]
    
    for file in files_to_include:
        if os.path.exists(file):
            cmd.extend(["--add-data", f"{file};."])

    cmd.append("server.py")
    
    print(f"Running command:\n{' '.join(cmd)}\n")
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n[SUCCESS] Build Successful! You can find the executable in the 'dist' folder.")
    else:
        print("\n[ERROR] Build Failed! Check the errors above.")

if __name__ == "__main__":
    build_exe()
