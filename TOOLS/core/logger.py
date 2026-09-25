import functools

def action_logger(tool_name):
    """Decorator to inject structured ACTION logs into the return string of tools."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Format arguments for the log
            arg_strs = [repr(a) for a in args]
            kwarg_strs = [f"{k}={repr(v)}" for k, v in kwargs.items()]
            all_args = ", ".join(arg_strs + kwarg_strs)
            
            log_start = f"[ACTION_START] Tool: {tool_name}\n[ACTION_CMD] {tool_name}({all_args})\n"
            
            try:
                result = func(*args, **kwargs)
                return f"{log_start}{result}\n[ACTION_END]"
            except Exception as e:
                return f"{log_start}Error executing tool: {str(e)}\n[ACTION_END]"
                
        return wrapper
    return decorator
