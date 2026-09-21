from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
c = OpenAI(
    api_key=os.getenv('GROK_API_KEY'),
    base_url=os.getenv('GROK_BASE_URL', 'https://api.groq.com/openai/v1')
)

models_to_try = [
    'openai/gpt-oss-120b',
    'openai/gpt-oss-20b',
    'qwen/qwen3.8-27b',
    'groq/compound',
    'groq/compound-mini',
]

results = []
for m in models_to_try:
    try:
        r = c.chat.completions.create(
            model=m,
            messages=[{'role': 'user', 'content': 'Say the word OK and nothing else.'}],
            max_tokens=5
        )
        results.append(f'SUCCESS: {m} -> {r.choices[0].message.content.strip()}')
    except Exception as e:
        results.append(f'FAIL [{m}]: {str(e)[:120]}')

with open('C:/Users/jasve/probe_results.txt', 'w', encoding='ascii', errors='replace') as f:
    f.write('\n'.join(results) + '\n')

print("Done.")
