import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from llama_cpp import Llama

base_model_path = r"F:\12_AI_MODELS\google\gemma-4-E4B-it-GGUF\gemma-4-E4B-it-Q4_K_M.gguf"

print("Loading LLM (Gemma) for Singlish test... Please wait.")
llm = Llama(
    model_path=base_model_path,
    n_ctx=2048,
    n_threads=0,
    n_threads_batch=0,
    n_batch=512,
    n_gpu_layers=30,
    use_mlock=False,
    use_mmap=True,
    echo=False,
    verbose=False
)
print("LLM Loaded Successfully!\n")

test_prompt = "Oya kohomada? Oya singlish walin katha karanna dannawada? Podi kavi kiyanna puluwanda?"
system_instruction = "You are a helpful AI. You MUST reply ONLY in Singlish (Sinhala written in English alphabet). Do not use English language sentences. Do not use Sinhala Unicode script. Write Sinhala words using English letters."
prompt = f"<start_of_turn>user\n{system_instruction}\n\nUser: {test_prompt}<end_of_turn>\n<start_of_turn>model\n"

print(f"User Question: {test_prompt}\n")
print("Generating Response...\n")

try:
    response = llm.create_completion(
        prompt=prompt,
        max_tokens=512,
        temperature=0.7,
        stop=["<end_of_turn>"]
    )
    
    output = response["choices"][0]["text"].strip()
    print("Model Response:")
    print("========================================")
    print(output)
    print("========================================")
except Exception as e:
    print(f"Error occurred: {e}")
