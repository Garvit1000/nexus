# jarvis.ai package
# Heavy AI clients (LLMClient, GoogleGenAIClient, OpenAIClient, etc.) are NOT
# imported at the package level. Import them explicitly in the files that need them:
#
#   from jarvis.ai.llm_client import GoogleGenAIClient
#   from jarvis.ai.command_generator import CommandGenerator
#
# This keeps `import jarvis.ai.decision_engine` lightweight for testing and
# for code that only needs intent classification without an LLM backend.
