from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Literal

logger = logging.getLogger(__name__)

ProviderName = Literal["anthropic", "openai", "ollama"]


class LLMClient:
    """Cliente LLM com import lazy dos SDKs por provedor."""

    def __init__(self, provider: ProviderName | None = None) -> None:
        raw = provider or os.environ.get("MONEYTREE_LLM_PROVIDER", "ollama")
        normalized = str(raw).strip().lower()
        if normalized not in ("anthropic", "openai", "ollama"):
            raise ValueError(f"MONEYTREE_LLM_PROVIDER inválido: {raw}")
        self.provider: ProviderName = normalized  # type: ignore[assignment]

    def complete(self, system: str, user: str) -> str:
        if self.provider == "anthropic":
            return self._complete_anthropic(system, user)
        if self.provider == "openai":
            return self._complete_openai(system, user)
        return self._complete_ollama(system, user)

    def _complete_anthropic(self, system: str, user: str) -> str:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY não definido")
        model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = []
        for block in message.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "".join(parts).strip()

    def _complete_openai(self, system: str, user: str) -> str:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY não definido")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        choice = response.choices[0].message.content
        return (choice or "").strip()

    def _complete_ollama(self, system: str, user: str) -> str:
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        request = urllib.request.Request(
            f"{base}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            logger.warning("Falha ao contatar Ollama: %s", exc)
            raise RuntimeError("Ollama indisponível") from exc
        msg = body.get("message") or {}
        return str(msg.get("content", "")).strip()
