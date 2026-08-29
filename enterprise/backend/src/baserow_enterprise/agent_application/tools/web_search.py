from typing import TYPE_CHECKING

from pydantic_ai import WebSearchTool

from .registries import AgentToolType

if TYPE_CHECKING:
    from ..deps import AgentRunDeps
    from ..models import AgentTool

# Provider-native web search is only available for these generative AI types
# (Anthropic and the OpenAI Responses API support pydantic-ai's WebSearchTool;
# Mistral/Ollama do not).
SUPPORTED_GENERATIVE_AI_TYPES = {"openai", "anthropic", "openrouter"}


def web_search_supported(generative_ai_type: str | None) -> bool:
    return generative_ai_type in SUPPORTED_GENERATIVE_AI_TYPES


class WebSearchAgentToolType(AgentToolType):
    type = "web_search"

    def get_builtin_tools(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        if not web_search_supported(deps.agent.ai_generative_ai_type):
            deps.system_notes.append(
                "Web search is enabled but not available for the configured "
                "model provider, so you cannot search the web."
            )
            return []
        return [WebSearchTool()]
