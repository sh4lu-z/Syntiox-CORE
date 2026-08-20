---
name: Semantic Codebase Search
description: Triggers when the user asks to find something conceptually in the codebase or search for code without knowing the exact file.
keywords: search, find, codebase, semantic, rag, where is, locate
---

# Semantic Codebase Search

When you need to find code, logic, or functions but don't know exactly which file it's in, you can use the Semantic Codebase Search tool. This tool uses `ChromaDB` and `sentence-transformers` to find files based on the *meaning* of your query, rather than exact text matches.

## How to use:
You MUST ALWAYS use this EXACT code structure to perform a semantic search:

```python
from TOOLS.search_utils import semantic_search_codebase

# Search the entire codebase for a concept
result = semantic_search_codebase("Where does the agent execute terminal commands?", n_results=3, directory=".")
print(result)
```

## Important Notes:
- The first time this runs, it will index all code files into `.chroma_db`, which might take a few seconds.
- It returns the file paths and the most relevant code chunks.
- If you get an error about missing modules, ensure `chromadb` and `sentence-transformers` are installed via `pip install -r requirements.txt`.
