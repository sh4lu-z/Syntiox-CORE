import os
import subprocess
import tempfile
import re
import ast

# Paths and keywords considered dangerous
DANGEROUS_PATHS = [
    r"c:\\windows", r"c:/windows",
    r"c:\\program files", r"c:/program files",
    r"c:\\program files (x86)", r"c:/program files (x86)"
]

DANGEROUS_KEYWORDS = [
    "os.system('del", "os.system('rm",
    "subprocess.run(['del", "subprocess.call(['del",
    "remove-item ", "del /", "rm -", "rmdir "
]

def analyze_code(code: str, code_type: str = "python") -> bool:
    """
    Analyzes the python code to see if it requires explicit user approval.
    Returns True if dangerous, False if safe to auto-execute.
    """
    code_lower = code.lower()
    
    # Check for dangerous paths
    for path in DANGEROUS_PATHS:
        if path in code_lower:
            return True
            
    # Check for destructive keywords
    for keyword in DANGEROUS_KEYWORDS:
        if keyword in code_lower:
            return True
            
    if code_type == "python":
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr in ['system', 'Popen']:
                            return True
                    elif isinstance(node.func, ast.Name):
                        if node.func.id in ['system', 'Popen']:
                            return True
        except SyntaxError:
            pass
            
    return False

def execute_code(code: str, code_type: str = "python") -> str:
    """
    Executes code based on its type (python or powershell).
    """
    
    # PowerShell execution
    if code_type == "powershell":
        workspace_dir = os.path.join(os.getcwd(), 'workspace')
        os.makedirs(workspace_dir, exist_ok=True)
        try:
            result = subprocess.run(
                ['powershell', '-Command', code], 
                capture_output=True, 
                text=True, 
                cwd=workspace_dir,
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += f"\nError: {result.stderr}"
            return output
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out after 30 seconds."
        except Exception as e:
            return f"Error executing powershell command: {str(e)}"

    # Python execution
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'input':
                    return "Error: The code contains 'input()'. You are running headlessly and this will cause a timeout hang. NEVER use input(). If you want to save a file, write a script to save it using 'with open()'."
    except SyntaxError:
        pass # If there's a syntax error, let Python execution catch it
    try:
        # Create a temporary python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name

        # Ensure workspace exists
        workspace_dir = os.path.join(os.getcwd(), 'workspace')
        os.makedirs(workspace_dir, exist_ok=True)
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        # Execute the file inside the workspace directory
        result = subprocess.run(
            ['python', temp_file_path], 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            cwd=workspace_dir,
            timeout=120, # Increased timeout for large tasks
            env=env
        )
        
        # Clean up the temp file
        os.remove(temp_file_path)
        
        output = result.stdout
        if result.stderr:
            output += f"\nError: {result.stderr}"
            
        return output
        
    except subprocess.TimeoutExpired:
        return "Error: Execution timed out after 30 seconds."
    except Exception as e:
        return f"Error executing code: {str(e)}"
