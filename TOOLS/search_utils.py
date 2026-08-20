import os
import glob
import re
from TOOLS.logger import action_logger

# Lazy loading for AI modules to prevent crashes on unsupported systems
chromadb = None
SentenceTransformer = None


CHROMA_DB_PATH = os.path.join(os.getcwd(), ".chroma_db")

# We use a lightweight model suitable for semantic search
MODEL_NAME = "all-MiniLM-L6-v2"
collection_name = "syntiox_codebase"

def index_codebase(directory=".", chunk_size=1000):
    """
    Scans the directory for code files, chunks them, and stores embeddings in ChromaDB.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        return f"Error: Failed to load AI models (chromadb/sentence-transformers). Is PyTorch installed correctly? Details: {e}"

    print("Initializing Semantic Codebase Search (This may take a moment to load the model)...")
    
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    # Check if collection already exists to avoid re-indexing unless necessary
    existing_collections = [c.name for c in client.list_collections()]
    if collection_name in existing_collections:
        client.delete_collection(collection_name)
        
    collection = client.create_collection(name=collection_name)
    model = SentenceTransformer(MODEL_NAME)
    
    allowed_extensions = {".py", ".md", ".json", ".html", ".js", ".css"}
    
    documents = []
    metadatas = []
    ids = []
    doc_id = 0
    
    print(f"Scanning directory: {directory}")
    for root, dirs, files in os.walk(directory):
        # Ignore common directories
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', '.chroma_db', 'venv', '.env']]
        
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in allowed_extensions:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # Very simple chunking
                        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
                        
                        for idx, chunk in enumerate(chunks):
                            if chunk.strip():
                                documents.append(chunk)
                                metadatas.append({"file": file_path, "chunk": idx})
                                ids.append(f"doc_{doc_id}")
                                doc_id += 1
                except Exception as e:
                    print(f"Failed to read {file_path}: {e}")
                    
    if not documents:
        return "No documents found to index."
        
    print(f"Generating embeddings for {len(documents)} chunks...")
    embeddings = model.encode(documents).tolist()
    
    print("Saving to ChromaDB...")
    collection.add(
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    return f"Successfully indexed {len(documents)} code chunks from the workspace."

def semantic_search_codebase(query: str, n_results: int = 5, directory: str = "."):
    """
    Searches the codebase semantically for the given query.
    If the index doesn't exist, it builds it first.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        return f"Error: Failed to load AI models (chromadb/sentence-transformers). Is PyTorch installed correctly? Details: {e}"
        
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        # Collection does not exist, need to index
        print("Codebase index not found. Indexing now...")
        index_result = index_codebase(directory=directory)
        if "Error" in index_result:
            return index_result
        collection = client.get_collection(name=collection_name)
        
    model = SentenceTransformer(MODEL_NAME)
    query_embedding = model.encode([query]).tolist()
    
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )
    
    if not results['documents'] or not results['documents'][0]:
        return "No relevant results found."
        
    output = f"🔍 SEMANTIC SEARCH RESULTS FOR: '{query}'\n{'='*50}\n\n"
    
    for i in range(len(results['documents'][0])):
        doc = results['documents'][0][i]
        meta = results['metadatas'][0][i]
        file_path = meta['file']
        
        output += f"📁 File: {file_path} (Chunk {meta['chunk']})\n"
        output += f"{'-'*50}\n"
        output += f"{doc}\n"
        output += f"{'='*50}\n\n"
        
    return output

@action_logger("grep_search")
def grep_search(query: str, directory: str = ".", is_regex: bool = False, case_insensitive: bool = True) -> str:
    """Searches for text or regex patterns in all files within a directory (similar to ripgrep)."""
    if not os.path.exists(directory):
        return f"Error: Directory '{directory}' not found."
        
    results = []
    flags = re.IGNORECASE if case_insensitive else 0
    
    # If it's not a regex, escape it so it's treated as literal text
    search_pattern = query if is_regex else re.escape(query)
    
    try:
        regex = re.compile(search_pattern, flags)
    except re.error as e:
        return f"Error: Invalid regex pattern '{query}': {str(e)}"
        
    for root, dirs, files in os.walk(directory):
        # Ignore common directories
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', '.chroma_db', 'venv', '.env']]
        
        for file in files:
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if regex.search(line):
                            results.append(f"{filepath}:{i+1}: {line.strip()[:150]}")
                            if len(results) >= 100:
                                return "\n".join(results) + f"\n... [Truncated. Over 100 matches found.]"
            except Exception:
                continue
                
    if not results:
        return f"No matches found for '{query}' in {directory}."
        
    return "\n".join(results)

if __name__ == "__main__":
    # Test execution
    print(index_codebase(".."))
    print(semantic_search_codebase("How to execute a terminal command?"))
