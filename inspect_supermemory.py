from supermemory import Supermemory
import inspect

print("Inspecting Supermemory SDK...")
client = Supermemory(api_key="dummy")

print(f"Client attributes: {dir(client)}")

if hasattr(client, 'memories'):
    print(f"\nMemoriesResource attributes: {dir(client.memories)}")
    
    # Check for likely candidates
    for attr in dir(client.memories):
        if not attr.startswith('_'):
            method = getattr(client.memories, attr)
            print(f"  - {attr}: {method}")

if hasattr(client, 'search'):
    print(f"\nSearchResource attributes: {dir(client.search)}")
