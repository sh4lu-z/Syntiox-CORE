---
name: Document Processing
description: Use when the user asks to read, summarize, or extract data from PDF, Word, Excel, or CSV files.
keywords: pdf, word, docx, excel, csv, read, summarize, document, docs, excel, spread
---

1. DOCUMENT PROCESSING INSTRUCTIONS:
- You have the ability to read various document formats by writing a short Python script to extract their text.
- If the user asks you to read a `.pdf`, you can use `PyMuPDF` (`fitz`) or `PyPDF2`. Use the `run_terminal_command` tool to run python scripts that read the file.
- If the user asks you to read a `.docx`, you can use `python-docx`.
- If the user asks you to read a `.csv` or `.xlsx`, use `pandas`.
- Always read the contents, print them, and then in your next step, provide the analysis or summary the user requested based on the `[EXECUTION RESULT]`.
- CRITICAL: Do NOT attempt to read very large files all at once. Read the first few pages/rows first to understand the structure, or summarize it in chunks.
