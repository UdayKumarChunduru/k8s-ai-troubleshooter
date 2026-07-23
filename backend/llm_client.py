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

_MAX_LOG_CHARS = 1500


def _truncate_logs(evidence: dict) -> dict:
    for pod in evidence.get("pods", []):
        for c in list(pod.get("containers", [])) + list(pod.get("init_containers", [])):
            for key in ("logs", "previous_logs"):
                text = c.get(key)
                if isinstance(text, str) and len(text) > _MAX_LOG_CHARS:
                    c[key] = "...[truncated, showing the last lines]...\n" + text[-_MAX_LOG_CHARS:]
    return evidence


def _user_prompt(evidence: dict, pattern: str) -> str:
    trimmed = _truncate_logs(evidence)
    evidence_str = json.dumps(trimmed)
    return f"Detected failure pattern: {pattern}\nEvidence:\n{evidence_str}"


def _parse(text: str) -> dict:
    # strip markdown fences some models wrap around JSON
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
        root_cause = str(data.get("root_cause", "")).strip()
        if not root_cause:
            return {
                "root_cause": (
                    "The model returned an empty response, most likely because the "
                    "evidence for this investigation was large enough to leave no room "
                    "in its context/output budget for an actual answer. Try again, or "
                    "increase OLLAMA_NUM_CTX / OLLAMA_NUM_PREDICT if this repeats for "
                    "this pattern."
                ),
                "confidence": 0,
                "fix_commands": [],
            }
        return {
            "root_cause": root_cause,
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
        self.num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))
        self.num_predict = int(os.environ.get("OLLAMA_NUM_PREDICT", "800"))

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
                "options": {
                    "num_ctx": self.num_ctx,
                    "num_predict": self.num_predict,
                },
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
