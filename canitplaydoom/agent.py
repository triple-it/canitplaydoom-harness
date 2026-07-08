"""Model adapter: a single OpenAI-compatible client for local (Ollama) and
cloud (OpenRouter) models.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass

SYSTEM_PROMPT = (
    "You are an agent playing the video game DOOM in the ViZDoom "
    "'defend_the_center' scenario. You stand in the center of a room and "
    "enemies approach from all sides. You must survive and kill as many "
    "enemies as possible. You perceive the world as an ASCII grid."
)


@dataclass
class Decision:
    action: str
    raw_response: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    parse_ok: bool


def build_prompt(observation: str, legend: dict, allowed_actions: list[str]) -> str:
    legend_lines = "\n".join(f"  {ch} = {desc}" for ch, desc in legend.items())
    actions = ", ".join(allowed_actions)
    return (
        f"ASCII view of the game (each character is a cell):\n\n{observation}\n\n"
        f"Legend:\n{legend_lines}\n\n"
        f"Allowed actions: {actions}.\n"
        "Choose exactly one action for this step. "
        'Respond ONLY with JSON: {"action": "<one_of_the_allowed_actions>"}.'
    )


def parse_action(text: str, allowed_actions: list[str], default: str) -> tuple[str, bool]:
    """Parse an action from model output. Returns (action, parse_ok)."""
    if not text:
        return default, False

    # 1) Try strict JSON anywhere in the text.
    for match in re.finditer(r"\{[^{}]*\}", text):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        action = str(obj.get("action", "")).strip().lower()
        if action in allowed_actions:
            return action, True

    # 2) Fall back to first allowed action keyword found.
    lowered = text.lower()
    positions = [(lowered.find(a), a) for a in allowed_actions if a in lowered]
    positions = [(p, a) for p, a in positions if p >= 0]
    if positions:
        positions.sort()
        return positions[0][1], True

    return default, False


class OllamaAgent:
    """Native Ollama /api/chat agent.

    Uses Ollama's native endpoint so we can set ``think: false`` for reasoning
    models (e.g. qwen3), which the OpenAI-compatible endpoint ignores. Uses only
    the standard library to avoid extra dependencies.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        think: bool = False,
        temperature: float = 0.2,
        max_tokens_per_step: int = 128,
        timeout: int = 120,
    ):
        root = base_url.rstrip("/")
        if root.endswith("/v1"):
            root = root[: -len("/v1")]
        self.api_url = root + "/api/chat"
        self.model = model
        self.think = think
        self.temperature = temperature
        self.max_tokens_per_step = max_tokens_per_step
        self.timeout = timeout

    def act(self, observation: str, legend: dict, allowed_actions: list[str]) -> Decision:
        import json as _json
        import urllib.request

        prompt = build_prompt(observation, legend, allowed_actions)
        default = allowed_actions[0]
        payload = {
            "model": self.model,
            "stream": False,
            "think": self.think,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens_per_step},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        raw = ""
        prompt_tokens = completion_tokens = 0
        start = time.time()
        try:
            req = urllib.request.Request(
                self.api_url,
                data=_json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = _json.loads(resp.read().decode())
            raw = (data.get("message") or {}).get("content", "") or ""
            prompt_tokens = data.get("prompt_eval_count", 0) or 0
            completion_tokens = data.get("eval_count", 0) or 0
        except Exception as exc:  # noqa: BLE001
            raw = f"__error__: {exc}"

        latency_ms = int((time.time() - start) * 1000)
        action, parse_ok = parse_action(raw, allowed_actions, default)
        return Decision(
            action=action,
            raw_response=raw,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            parse_ok=parse_ok,
        )


class Agent:
    """OpenAI-compatible chat agent."""

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key_env: str | None = None,
        temperature: float = 0.2,
        max_tokens_per_step: int = 64,
    ):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Install the 'openai' package: pip install openai") from exc

        api_key = os.environ.get(api_key_env, "") if api_key_env else "ollama"
        # Ollama accepts any non-empty key; OpenRouter needs the real one.
        self._client = OpenAI(base_url=base_url, api_key=api_key or "none")
        self.model = model
        self.temperature = temperature
        self.max_tokens_per_step = max_tokens_per_step

    def act(self, observation: str, legend: dict, allowed_actions: list[str]) -> Decision:
        prompt = build_prompt(observation, legend, allowed_actions)
        default = allowed_actions[0]
        start = time.time()
        raw = ""
        prompt_tokens = completion_tokens = 0
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens_per_step,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = resp.choices[0].message.content or ""
            if resp.usage:
                prompt_tokens = resp.usage.prompt_tokens or 0
                completion_tokens = resp.usage.completion_tokens or 0
        except Exception as exc:  # noqa: BLE001 - a failed call must not crash the run
            raw = f"__error__: {exc}"

        latency_ms = int((time.time() - start) * 1000)
        action, parse_ok = parse_action(raw, allowed_actions, default)
        return Decision(
            action=action,
            raw_response=raw,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            parse_ok=parse_ok,
        )
