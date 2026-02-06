from supermemory import Supermemory

print("Testing client.add()...")
client = Supermemory(api_key="dummy_key_for_structure_test")

# usage based on inspection
try:
    # We expect this to fail with Auth error, but NOT with AttributeError
    client.add(
        content="Test memory",
        metadata={"test": "true"}
    )
    print("Success (or at least method exists)")
except AttributeError as e:
    print(f"AttributeError: {e}")
except Exception as e:
    print(f"Other Error (Expected): {e}")
