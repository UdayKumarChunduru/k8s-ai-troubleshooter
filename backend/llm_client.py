import json
import os

import requests

SYSTEM_PROMPT = (
    "You are a Kubernetes troubleshooting assistant. You receive pod states, "
    "container logs and cluster events. Reply with JSON only, using exactly "
    "these keys: root_cause (string, two to four sentences), confidence "
    "(integer 0 to 100), fix_commands (array of kubectl or shell command strings). "
    "Base the fix commands on the actual namespace and resource names in the evidence."
)


def _user_prompt(evidence: dict, pattern: str) -> str:
    return (
        f"Detected failure pattern: {pattern}\n"
        f"Evidence:\n{json.dumps(evidence, indent=1)[:12000]}"
    )


def _parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
        return {
            "root_cause": str(data.get("root_cause", "")),
            "confidence": int(data.get("confidence", 50)),
            "fix_commands": [str(c) for c in data.get("fix_commands", [])],
        }
    except (json.JSONDecodeError, ValueError):
        return {"root_cause": text, "confidence": 40, "fix_commands": []}


class OpenRouterProvider:
    URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self):
        self.api_key = os.environ["OPENROUTER_API_KEY"]
        self.model = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")

    def analyze(self, evidence: dict, pattern: str) -> dict:
        resp = requests.post(
            self.URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _user_prompt(evidence, pattern)},
                ],
                "temperature": 0.2,
            },
            timeout=90,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _parse(text)


class OllamaProvider:

    def __init__(self):
        self.base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
        self.timeout = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "300"))

    def analyze(self, evidence: dict, pattern: str) -> dict:
        prompt = f"{SYSTEM_PROMPT}\n\n{_user_prompt(evidence, pattern)}"
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "think": False,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        text = resp.json()["response"]
        return _parse(text)


class BedrockProvider:

    def __init__(self):
        import boto3

        self.region = os.environ.get("BEDROCK_REGION", "us-east-1")
        self.model_id = os.environ.get(
            "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
        self._client = boto3.client("bedrock-runtime", region_name=self.region)

    def analyze(self, evidence: dict, pattern: str) -> dict:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": _user_prompt(evidence, pattern)}
            ],
        }
        response = self._client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        text = payload["content"][0]["text"]
        return _parse(text)


_PROVIDERS = {
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
    "bedrock": BedrockProvider,
}


def _get_provider():
    name = os.environ.get("LLM_PROVIDER", "openrouter")
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER '{name}', expected one of {list(_PROVIDERS)}")
    return _PROVIDERS[name]()


def analyze(evidence: dict, pattern: str) -> dict:
    provider = _get_provider()
    return provider.analyze(evidence, pattern)
