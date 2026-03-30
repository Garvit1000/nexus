import logging
from typing import Optional
from ..core.security import scrub_credentials


class SupermemoryClient:
    def __init__(self, api_key: str):
        try:
            from supermemory import Supermemory
        except ImportError:
            raise ImportError(
                "Supermemory SDK not installed. Run 'pip install supermemory'"
            )

        self.client = Supermemory(api_key=api_key)

    def add_memory(self, content: str, metadata: Optional[dict] = None) -> bool:
        """
        Adds a new memory to Supermemory using the official SDK.
        Credentials are scrubbed before storage.
        """
        try:
            safe_content = scrub_credentials(content)
            safe_metadata = {}
            if metadata:
                for k, v in metadata.items():
                    safe_metadata[k] = scrub_credentials(v) if isinstance(v, str) else v
            self.client.add(content=safe_content, metadata=safe_metadata)
            return True
        except Exception as e:
            logging.error(f"Failed to add memory: {e}")
            return False

    def query_memory(self, query: str, limit: int = 3, time_decay: bool = True) -> str:
        """
        Retrieves relevant context for a query using the official SDK.

        Args:
            query: The search query
            limit: Maximum number of results to return
            time_decay: If True, prioritize recent memories (Logic handled by engine if possible)
        """
        try:
            # SDK usage: client.search.execute(q=...)
            response = self.client.search.execute(q=query)

            # response.results should be a list of dicts or objects
            # Based on user snippet: print(searching.results)
            if hasattr(response, "results"):
                results = response.results
            else:
                results = response.get("results", [])

            if not results:
                return ""

            # Helper to extract content safely whether it's an object or dict
            def get_content(item):
                content = None
                # Try common attribute names
                for attr in ["content", "document", "text", "page_content"]:
                    if isinstance(item, dict):
                        content = item.get(attr)
                    else:
                        content = getattr(item, attr, None)
                    if content:
                        break

                # Fallback to string representation if still None
                if content is None:
                    # logging.warning(f"Could not extract content from memory item: {item}")
                    return str(item)
                return str(content)

            context_str = "\n".join(
                [f"- {get_content(item)}" for item in results[:limit]]
            )
            return f"Relevant Context from Memory:\n{context_str}\n"
        except Exception as e:
            logging.error(f"Failed to query memory: {e}")
            return ""

    def log_execution(self, query: str, plan: list, status: str, output: str) -> bool:
        """
        Logs a full task execution lifecycle to Supermemory.
        """
        import json
        from dataclasses import asdict, is_dataclass

        try:
            safe_query = scrub_credentials(query)
            safe_output = scrub_credentials(output[:500])
            content = f"Task Execution Log:\nQuery: {safe_query}\nOutcome: {status}\nOutput: {safe_output}..."

            # Convert plan to dict - handle both dataclass and dict objects
            plan_data = []
            if plan:
                for p in plan:
                    if is_dataclass(p):
                        plan_data.append(asdict(p))
                    elif isinstance(p, dict):
                        plan_data.append(p)
                    else:
                        plan_data.append(str(p))

            metadata = {
                "type": "task_log",
                "status": status,
                "plan": scrub_credentials(json.dumps(plan_data)),
                "query": safe_query,
            }
            return self.add_memory(content, metadata)
        except Exception as e:
            logging.error(f"Failed to log execution: {e}")
            return False

    def retrieve_context(self, query: str) -> str:
        """
        Retrieves specific technical context: Past Plans and Past Errors.
        """
        plans = self.query_memory(f"plan for {query}", limit=2)
        errors = self.query_memory(f"error in {query}", limit=2)

        context = ""
        if "Relevant Context" in plans:
            context += f"\n### 🧠 RELEVANT PAST PLANS:\n{plans}\n"
        if "Relevant Context" in errors:
            context += f"\n### ⚠️ PAST ERRORS & FIXES:\n{errors}\n"

        return context


class MockMemoryClient(SupermemoryClient):
    def __init__(self):
        pass

    def add_memory(self, content: str, metadata: Optional[dict] = None) -> bool:
        # print(f"[Mock] Added memory: {content}")
        return True

    def query_memory(self, query: str, limit: int = 3) -> str:
        return ""

    def log_execution(self, query: str, plan: list, status: str, output: str) -> bool:
        return True

    def retrieve_context(self, query: str) -> str:
        return ""
