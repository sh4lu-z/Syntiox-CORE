---
name: Semantic Codebase Search
description: Triggers when the user asks to find something conceptually in the codebase or search for code without knowing the exact file.
keywords: search, find, codebase, semantic, rag, where is, locate
---

# Semantic Codebase Search

When you need to find code, logic, or functions but don't know exactly which file it's in, you can use the Semantic Codebase Search tool. This tool uses `ChromaDB` and `sentence-transformers` to find files based on the *meaning* of your query, rather than exact text matches.

## How to use:
Call the native tools directly via Native Function Calling (do NOT write a Python script to import them):

1. **`semantic_search_codebase(query: str, n_results: int = 5, directory: str = ".")`**
   - Searches the codebase conceptually for the meaning of `query`.
   - Automatically builds the ChromaDB index in `.chroma_db` if it doesn't exist yet.
2. **`index_codebase(directory: str = ".", chunk_size: int = 1000, force: bool = False)`**
   - Rebuilds the semantic search index (pass `force=True` to re-index after major code changes).
3. **`grep_search(query: str, directory: str = ".", is_regex: bool = False, case_insensitive: bool = True)`**
   - Fast exact text or regex search across files when you know the symbol or string name.

## Important Notes:
- The first time `semantic_search_codebase` runs, it indexes code files into `.chroma_db`, which might take a few seconds.
- It returns the file paths and the most relevant code chunks.
