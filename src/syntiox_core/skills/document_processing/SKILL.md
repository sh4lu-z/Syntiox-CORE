---
name: document_processing
description: Use when the user asks to read, summarize, or extract data from PDF, Word, Excel, or CSV files.
keywords: pdf, word, docx, excel, csv, read, summarize, document, docs, spread
---

1. DOCUMENT PROCESSING INSTRUCTIONS:
- You have the ability to read various document formats by saving a short Python script with `write_to_file` and executing it via `run_terminal_command("python read_doc.py")` (do NOT use `python -c`). Clean up the temporary script when finished.
- If the user asks you to read a `.pdf`, you can use `PyMuPDF` (`fitz`).
- If the user asks you to read a `.docx`, you can use `python-docx`.
- If the user asks you to read a `.csv` or `.xlsx`, use `pandas`.
- Always read the contents, print them, and then in your next step, provide the analysis or summary the user requested based on the tool result.
- CRITICAL: Do NOT attempt to read very large files all at once. Read the first few pages/rows first to understand the structure, or summarize it in chunks.
