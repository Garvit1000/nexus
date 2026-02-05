
import os
from google import genai

api_key = os.getenv("JARVIS_API_KEY")
if not api_key:
    # Fallback to manual .env reading if env var is missing
    try:
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("JARVIS_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    except:
        pass

if not api_key:
    print("Error: JARVIS_API_KEY not found.")
    exit(1)

print(f"Using Key: {api_key[:5]}...")

try:
    client = genai.Client(api_key=api_key)
    print("Listing available models...")
    # Paginating or iterating to find valid models
    count = 0
    for m in client.models.list(config={"page_size": 100}):
        print(f"Found: {m.name}")

except Exception as e:
    print(f"Error listing models: {e}")
