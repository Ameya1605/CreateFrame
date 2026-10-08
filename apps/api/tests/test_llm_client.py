import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from llm_client import LLMClient
import brain
import models
import auth
from database import Base, engine, get_db
from main import app, get_user_from_header

client = TestClient(app)


def test_extract_json_direct():
    data = {"status": "ok", "count": 42}
    result = LLMClient.extract_json(json.dumps(data))
    assert result == data


def test_extract_json_markdown_blocks():
    # json block
    raw = "```json\n{\n  \"tables\": [\"users\", \"posts\"]\n}\n```"
    result = LLMClient.extract_json(raw)
    assert result == {"tables": ["users", "posts"]}

    # generic code block
    raw2 = "```\n[\"feature1\", \"feature2\"]\n```"
    result2 = LLMClient.extract_json(raw2)
    assert result2 == ["feature1", "feature2"]


def test_extract_json_surrounded_by_prose():
    raw = "Sure, here is your requested architectural layout:\n{\"tables\": [\"teams\"], \"routes\": [\"/teams\"]}\nLet me know if you need anything else!"
    result = LLMClient.extract_json(raw)
    assert result == {"tables": ["teams"], "routes": ["/teams"]}


def test_extract_json_invalid_raises():
    with pytest.raises(ValueError):
        LLMClient.extract_json("not valid json at all")


def test_llm_client_initialization():
    groq_client = LLMClient(provider="groq", api_key="test_key")
    assert groq_client.provider == "groq"
    assert groq_client.api_key == "test_key"
    assert groq_client.is_configured() is True

    ollama_client = LLMClient(provider="ollama")
    assert ollama_client.provider == "ollama"
    assert ollama_client.is_configured() is True


def test_llm_client_openai_compatible_call():
    llm = LLMClient(provider="openai", api_key="sk-test", model="gpt-4o-mini")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "{\"result\": \"success\"}"}}]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = llm.complete([{"role": "user", "content": "hello"}])
        assert res == "{\"result\": \"success\"}"


def test_llm_client_anthropic_call():
    llm = LLMClient(provider="anthropic", api_key="sk-ant-test", model="claude-3-5-sonnet-latest")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": "Anthropic response"}]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = llm.complete([{"role": "user", "content": "hi"}])
        assert res == "Anthropic response"


def test_brain_completion_adapter():
    fake_client = LLMClient(provider="ollama")
    with patch.object(fake_client, "complete", return_value="{\"foo\": \"bar\"}"):
        res = brain.create_completion(fake_client, messages=[{"role": "user", "content": "test"}])
        assert res.choices[0].message.content == "{\"foo\": \"bar\"}"


def test_llm_config_endpoints(db_session=None):
    # Mock user dependency
    test_user = models.User(
        id=999,
        github_id=999,
        username="llm_tester",
        encrypted_github_token="fake_token",
        llm_provider="groq",
        llm_model=None,
        encrypted_llm_api_key=None,
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = test_user
    app.dependency_overrides[get_user_from_header] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: mock_db

    # GET initial config
    res = client.get("/users/me/llm-config")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "groq"
    assert data["has_api_key"] is False

    # PUT new config with OpenAI
    update_res = client.put(
        "/users/me/llm-config",
        json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-real-key"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["provider"] == "openai"
    assert update_res.json()["model"] == "gpt-4o"
    assert update_res.json()["has_api_key"] is True
    assert test_user.llm_provider == "openai"
    assert test_user.llm_model == "gpt-4o"
    assert test_user.encrypted_llm_api_key is not None

    # PUT invalid provider
    invalid_res = client.put(
        "/users/me/llm-config",
        json={"provider": "unsupported_provider"}
    )
    assert invalid_res.status_code == 400

    app.dependency_overrides.clear()
