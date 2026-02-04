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
        return self._parse_response(response_text)

    def _build_prompt(self, request: str) -> str:
        return f"""
You are a Linux Terminal Assistant.
System Info: {self.system_info.os_name} {self.system_info.os_version}
Package Manager: {self.system_info.package_manager.value}

User Request: "{request}"

Task: Generate the best single CLI command to fulfill the request.
Rules:
1. Return ONLY the command. No markdown, no explanations.
2. If multiple commands are needed, chain them with &&.
3. Use sudo if strictly necessary.
4. Prefer the system native package manager ({self.system_info.package_manager.value}).

Command:
"""

    def _parse_response(self, response: str) -> str:
        # Cleanup any markdown or extra whitespace
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        return cleaned.strip()
