import pytest
from coldquery.prompts.analyze_query import analyze_query_performance
from coldquery.prompts.debug_locks import debug_lock_contention
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_analyze_query_performance_prompt():
    ctx = MagicMock()
    sql = "SELECT * FROM users WHERE id = 1"
    prompt = await analyze_query_performance(sql, ctx)
    assert isinstance(prompt, list)
    assert len(prompt) == 1

    # Message object assertions
    assert hasattr(prompt[0], "role")
    assert prompt[0].role == "user"

    assert hasattr(prompt[0], "content")
    # content might be TextContent object or string depending on normalization,
    # but based on traceback it is TextContent
    content_text = prompt[0].content.text if hasattr(prompt[0].content, "text") else prompt[0].content
    assert sql in content_text

@pytest.mark.asyncio
async def test_debug_lock_contention_prompt():
    ctx = MagicMock()
    prompt = await debug_lock_contention(ctx)
    assert isinstance(prompt, list)
    assert len(prompt) == 1

    assert hasattr(prompt[0], "role")
    assert prompt[0].role == "user"

    assert hasattr(prompt[0], "content")
    content_text = prompt[0].content.text if hasattr(prompt[0].content, "text") else prompt[0].content
    assert "lock contention" in content_text
