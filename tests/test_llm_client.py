import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import llm_client  # noqa: E402


def test_parse_clean_json():
    text = json.dumps({"root_cause": "bad image tag", "confidence": 90, "fix_commands": ["kubectl get pods"]})
    result = llm_client._parse(text)
    assert result["root_cause"] == "bad image tag"
    assert result["confidence"] == 90
    assert result["fix_commands"] == ["kubectl get pods"]


def test_parse_strips_markdown_fence():
    text = "```json\n" + json.dumps({"root_cause": "x", "confidence": 50, "fix_commands": []}) + "\n```"
    result = llm_client._parse(text)
    assert result["root_cause"] == "x"


def test_parse_falls_back_on_non_json():
    text = "The pod is crashing because of a bad config."
    result = llm_client._parse(text)
    assert result["root_cause"] == text
    assert result["confidence"] == 40
    assert result["fix_commands"] == []


@patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
@patch("llm_client.requests.post")
def test_openrouter_provider(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(
            {"root_cause": "oom", "confidence": 80, "fix_commands": ["kubectl top pods"]}
        )}}]
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    provider = llm_client.OpenRouterProvider()
    result = provider.analyze({"namespace": "default"}, "OOMKilled")

    assert result["root_cause"] == "oom"
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


@patch("llm_client.requests.post")
def test_ollama_provider(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": json.dumps({"root_cause": "bad probe", "confidence": 70, "fix_commands": []})
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    provider = llm_client.OllamaProvider()
    result = provider.analyze({"namespace": "default"}, "ReadinessProbe")

    assert result["root_cause"] == "bad probe"
    called_url = mock_post.call_args.args[0]
    assert called_url.endswith("/api/generate")


@patch("llm_client.boto3", create=True)
def test_bedrock_provider(mock_boto3):
    fake_body = MagicMock()
    fake_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps({"root_cause": "node pressure", "confidence": 60, "fix_commands": []})}]
    }).encode()
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = {"body": fake_body}
    mock_boto3.client.return_value = mock_client

    with patch.dict(sys.modules, {"boto3": mock_boto3}):
        provider = llm_client.BedrockProvider()
        result = provider.analyze({"namespace": "default"}, "Pending/ResourcePressure")

    assert result["root_cause"] == "node pressure"
    mock_client.invoke_model.assert_called_once()


def test_unknown_provider_raises():
    with patch.dict(os.environ, {"LLM_PROVIDER": "not-a-real-provider"}):
        try:
            llm_client._get_provider()
            assert False, "expected ValueError"
        except ValueError:
            pass
