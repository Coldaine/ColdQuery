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
    assert "role" in prompt[0]
    assert "content" in prompt[0]
    assert sql in prompt[0]["content"]

@pytest.mark.asyncio
async def test_debug_lock_contention_prompt():
    ctx = MagicMock()
    prompt = await debug_lock_contention(ctx)
    assert isinstance(prompt, list)
    assert len(prompt) == 1
    assert "role" in prompt[0]
    assert "content" in prompt[0]
    assert "lock contention" in prompt[0]["content"]
