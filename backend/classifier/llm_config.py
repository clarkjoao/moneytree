from __future__ import annotations

import json
import os
from pathlib import Path
_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "llm_config.json"

_DEFAULTS: dict[str, str] = {
    "provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "qwen2.5:7b",
    "anthropic_model": "claude-3-5-haiku-20241022",
    "openai_model": "gpt-4o-mini",
    "anthropic_api_key": "",
    "openai_api_key": "",
}


def load_llm_config() -> dict[str, str]:
    """Carrega config do arquivo, com fallback para env vars e defaults."""
    config = dict(_DEFAULTS)

    if _CONFIG_PATH.exists():
        try:
            stored = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            config.update({k: str(v) if v is not None else "" for k, v in stored.items() if k in _DEFAULTS})
        except Exception:
            pass

    env_map = {
        "MONEYTREE_LLM_PROVIDER": "provider",
        "OLLAMA_BASE_URL": "ollama_base_url",
        "OLLAMA_MODEL": "ollama_model",
        "ANTHROPIC_MODEL": "anthropic_model",
        "OPENAI_MODEL": "openai_model",
        "ANTHROPIC_API_KEY": "anthropic_api_key",
        "OPENAI_API_KEY": "openai_api_key",
    }
    for env_key, config_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            config[config_key] = val

    return config


def save_llm_config(config: dict[str, object]) -> None:
    """Persiste configuração em arquivo. Não sobrescreve chave API com string vazia."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(_DEFAULTS)
    if _CONFIG_PATH.exists():
        try:
            stored = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            merged.update({k: str(v) if v is not None else "" for k, v in stored.items() if k in _DEFAULTS})
        except Exception:
            pass

    for key, value in config.items():
        if key not in _DEFAULTS:
            continue
        if key.endswith("_api_key"):
            if value is None or str(value).strip() == "":
                continue
        merged[key] = str(value) if value is not None else ""

    _CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def build_llm_client_from_config():
    """Instancia LLMClient com a configuração atual (arquivo + env vars + defaults)."""
    from backend.classifier.llm_client import LLMClient

    cfg = load_llm_config()

    os.environ["MONEYTREE_LLM_PROVIDER"] = cfg["provider"]
    os.environ["OLLAMA_BASE_URL"] = cfg["ollama_base_url"]
    os.environ["OLLAMA_MODEL"] = cfg["ollama_model"]
    os.environ["ANTHROPIC_MODEL"] = cfg["anthropic_model"]
    os.environ["OPENAI_MODEL"] = cfg["openai_model"]
    if cfg.get("anthropic_api_key"):
        os.environ["ANTHROPIC_API_KEY"] = cfg["anthropic_api_key"]
    if cfg.get("openai_api_key"):
        os.environ["OPENAI_API_KEY"] = cfg["openai_api_key"]

    return LLMClient(provider=cfg["provider"])  # type: ignore[arg-type]
