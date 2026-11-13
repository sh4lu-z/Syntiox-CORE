---
name: Codebase Search
description: Triggers when the user asks to find something in the codebase, search for functions, or locate files.
keywords: search, find, codebase, locate, grep, where is, symbol
---

# Codebase Search

When you need to find code, logic, functions, or specific symbols across the codebase, use the fast text and pattern matching tools:

## How to use:
Call the native tools directly via Native Function Calling:

1. **`grep_search(query: str, directory: str = ".", is_regex: bool = False, case_insensitive: bool = True)`**
   - Fast text or regular expression search across code files (similar to ripgrep).
   - Use when searching for function names, class definitions, imports, routes, or error strings.

2. **`find_files_by_name(pattern: str, directory: str = ".")`**
   - Finds files by a glob pattern (e.g., `*.py`, `config.*`, `*controller*`) recursively.

3. **`search_in_files(query: str, directory: str = ".")`**
   - Substring search across all text files within a directory.
