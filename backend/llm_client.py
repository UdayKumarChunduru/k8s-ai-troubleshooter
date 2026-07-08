import json
import os

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")

SYSTEM_PROMPT = (
    "You are a Kubernetes troubleshooting assistant. You receive pod states, "
    "container logs and cluster events. Reply with JSON only, using exactly "
    "these keys: root_cause (string, two to four sentences), confidence "
    "(integer 0 to 100), fix_commands (array of kubectl or shell command strings). "
    "Base the fix commands on the actual namespace and resource names in the evidence."
)


def analyze(evidence: dict, pattern: str) -> dict:
    api_key = os.environ["OPENROUTER_API_KEY"]

    user_prompt = (
        f"Detected failure pattern: {pattern}\n"
        f"Evidence:\n{json.dumps(evidence, indent=1)[:12000]}"
    )

    resp = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        },
        timeout=90,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()

    return _parse(text)


def _parse(text: str) -> dict:
    # strip markdown fences some models wrap around JSON
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
