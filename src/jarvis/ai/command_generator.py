import json
from .llm_client import LLMClient
from ..core.system_detector import SystemInfo

class CommandGenerator:
    def __init__(self, llm_client: LLMClient, system_info: SystemInfo):
        self.llm = llm_client
        self.system_info = system_info

    def generate_command(self, user_request: str) -> str:
        """
        Converts a natural language request into a shell command.
        """
        prompt = self._build_prompt(user_request)
        response_text = self.llm.generate_response(prompt)
        command = self._parse_response(response_text)
        
        # Automatically save successful generations to memory if available
        # We assume if we generated a command, it's a valid interaction worth remembering
        if self.llm.memory_client:
            self.llm.memory_client.add_memory(
                content=f"User requested: '{user_request}'. Nexus generated: '{command}'",
                metadata={"type": "command_generation", "os": self.system_info.os_name}
            )
            
        return command

    def _build_prompt(self, request: str) -> str:
        return f"""
You are Nexus, an elite intelligent Linux Assistant.
Your purpose is to autonomously design and generate safe, efficient, and robust CLI solutions.

### SYSTEM CONTEXT
- OS: {self.system_info.os_name} {self.system_info.os_version}
- Package Manager: {self.system_info.package_manager.value}

### INTELLIGENCE CORE & MEMORY
You have access to a persistent memory stream (provided above).
1. **Context Absorption**: Read the "MEMORY CONTEXT" provided above carefully.
2. **Preference Recognition**: Identify user habits (e.g., "user likes podman over docker", "user uses zsh").
3. **Continuous Improvement**: If the context shows a past failure for a similar task, ADAPT your strategy. Do not repeat mistakes.

### DESIGN PHILOSOPHY
1. **Idempotency**: Where possible, generate commands that can be run multiple times safely.
2. **Modularity**: Chain small tools (`grep`, `awk`, `xargs`) rather than complex custom logic.
3. **Safety**: NEVER run destructive commands (`rm -rf /`) without safeguards or explicit user intent.
4. **Efficiency**: Use the most modern tools available on the system.

### OUTPUT RULES
- Return **ONLY** the executable CLI command string.
- NO markdown code blocks (```).
- NO introductory text or explanations.
- If multiple steps are required, join them logically with `&&` or `;`.

### USER REQUEST
"{request}"

### GENERATED SOLUTION
"""

    def _parse_response(self, response: str) -> str:
        # Cleanup any markdown or extra whitespace
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.replace("`", "") # Remove inline code ticks if any
        return cleaned.strip()
