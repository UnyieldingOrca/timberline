"""Deep agent for log analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from deepagents import create_deep_agent
from loguru import logger


@dataclass
class AnalysisResult:
    """Result of an agent analysis run."""

    summary: str
    tool_calls_made: int = 0
    turns_used: int = 0
    errors: list[str] = field(default_factory=list)


def _build_llm(model: str, api_key: str | None = None) -> Any:
    """Build a LangChain chat model via OpenRouter (OpenAI-compatible)."""
    from langchain.chat_models import init_chat_model

    kwargs: dict[str, Any] = {"base_url": "https://openrouter.ai/api/v1"}
    if api_key:
        kwargs["api_key"] = api_key
    return init_chat_model(f"openai:{model}", **kwargs)


async def run_agent(
    tools: list,
    system_prompt: str,
    user_prompt: str,
    model: str = "anthropic/claude-sonnet-4",
    api_key: str | None = None,
    max_turns: int = 50,
) -> AnalysisResult:
    """Run the deep agent with the given tools and prompts."""
    llm = _build_llm(model, api_key)
    agent = create_deep_agent(model=llm, tools=tools, system_prompt=system_prompt)

    logger.info(f"Starting agent with {len(tools)} tools (model: {model})")

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_prompt}]},
        config={"recursion_limit": max_turns},
    )

    output_messages = result.get("messages", [])
    final_text = ""
    tool_calls_made = 0
    for msg in output_messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_calls_made += len(msg.tool_calls)
        if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content:
            final_text = msg.content

    return AnalysisResult(
        summary=final_text,
        tool_calls_made=tool_calls_made,
        turns_used=len(output_messages),
    )
