"""Tests for the deep agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from timberline.agent import AnalysisResult, run_agent


@pytest.mark.asyncio
async def test_run_agent_returns_result():
    """run_agent returns an AnalysisResult with content from the agent."""
    mock_ai_msg = MagicMock()
    mock_ai_msg.content = "Analysis complete: all systems healthy."
    mock_ai_msg.tool_calls = []

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {"messages": [mock_ai_msg]}

    with patch("timberline.agent.create_deep_agent", return_value=mock_agent):
        with patch("timberline.agent._build_llm", return_value=MagicMock()):
            result = await run_agent(
                tools=[lambda: None],
                system_prompt="You are a test agent.",
                user_prompt="Analyze logs",
                model="test-model",
                api_key="test-key",
                max_turns=5,
            )

    assert isinstance(result, AnalysisResult)
    assert result.summary == "Analysis complete: all systems healthy."
    assert result.tool_calls_made == 0


@pytest.mark.asyncio
async def test_run_agent_counts_tool_calls():
    """run_agent correctly counts tool calls from messages."""
    mock_tool_msg = MagicMock()
    mock_tool_msg.content = ""
    mock_tool_msg.tool_calls = [{"name": "test_tool", "args": {"message": "hi"}}]

    mock_tool_result = MagicMock()
    mock_tool_result.content = "tool says: hi"
    mock_tool_result.tool_calls = []

    mock_final_msg = MagicMock()
    mock_final_msg.content = "Done analyzing."
    mock_final_msg.tool_calls = []

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [mock_tool_msg, mock_tool_result, mock_final_msg]
    }

    with patch("timberline.agent.create_deep_agent", return_value=mock_agent):
        with patch("timberline.agent._build_llm", return_value=MagicMock()):
            result = await run_agent(
                tools=[lambda: None],
                system_prompt="Test",
                user_prompt="Analyze",
                max_turns=5,
            )

    assert result.summary == "Done analyzing."
    assert result.tool_calls_made == 1
    assert result.turns_used == 3
