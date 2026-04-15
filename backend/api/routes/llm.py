from __future__ import annotations

import json
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from backend.classifier.llm_config import _DEFAULTS, load_llm_config, save_llm_config

router = APIRouter()


class LLMConfigPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    anthropic_model: str | None = None
    openai_model: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


def _mask_key(key: str) -> str:
    if len(key) > 12:
        return key[:8] + "..." + key[-4:]
    return "****"


def _is_masked_or_placeholder(api_key: str) -> bool:
    stripped = api_key.strip()
    if not stripped:
        return True
    return "..." in stripped


@router.get("/llm/config")
def get_llm_config():
    raw = load_llm_config()
    out = {k: raw.get(k, _DEFAULTS[k]) for k in _DEFAULTS}

    if out.get("anthropic_api_key"):
        out["anthropic_api_key"] = _mask_key(out["anthropic_api_key"])
        out["anthropic_api_key_set"] = True
    else:
        out["anthropic_api_key_set"] = False
        out["anthropic_api_key"] = ""

    if out.get("openai_api_key"):
        out["openai_api_key"] = _mask_key(out["openai_api_key"])
        out["openai_api_key_set"] = True
    else:
        out["openai_api_key_set"] = False
        out["openai_api_key"] = ""

    return out


@router.put("/llm/config")
def update_llm_config(payload: LLMConfigPayload):
    valid_providers = ("anthropic", "openai", "ollama")
    if payload.provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Provider inválido: {payload.provider}")

    update = payload.model_dump(exclude_none=True)
    save_llm_config(update)
    return {"status": "saved"}


@router.post("/llm/test")
def test_llm_connection(payload: LLMConfigPayload):
    provider = payload.provider
    if provider == "ollama":
        return _test_ollama(payload.ollama_base_url or "http://localhost:11434")

    if provider == "anthropic":
        return _test_anthropic(payload)

    if provider == "openai":
        return _test_openai(payload)

    raise HTTPException(status_code=400, detail="Provider inválido")


def _test_ollama(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        models = [m["name"] for m in body.get("models", [])]
        if not models:
            return {
                "ok": True,
                "message": "Ollama está rodando, mas nenhum modelo instalado.",
                "models": [],
            }
        return {
            "ok": True,
            "message": f"{len(models)} modelo(s) disponível(is).",
            "models": models,
        }
    except urllib.error.URLError:
        return {
            "ok": False,
            "message": f"Ollama não encontrado em {base_url}. Verifique se está rodando.",
            "models": None,
        }
    except Exception as exc:
        return {"ok": False, "message": f"Erro inesperado: {exc}", "models": None}


def _test_anthropic(payload: LLMConfigPayload) -> dict:
    api_key = (payload.anthropic_api_key or "").strip()
    if _is_masked_or_placeholder(api_key):
        saved = load_llm_config().get("anthropic_api_key", "")
        if not saved:
            return {"ok": False, "message": "Chave API Anthropic não configurada.", "models": None}
        api_key = saved

    model = (payload.anthropic_model or load_llm_config().get("anthropic_model") or "").strip()
    if not model:
        model = "claude-3-5-haiku-20241022"

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        return {"ok": True, "message": "Conexão com Anthropic bem-sucedida.", "models": None}
    except Exception as exc:
        msg = str(exc)
        if "401" in msg or "authentication" in msg.lower():
            return {"ok": False, "message": "Chave API inválida ou sem permissão.", "models": None}
        return {"ok": False, "message": f"Erro: {msg[:120]}", "models": None}


def _test_openai(payload: LLMConfigPayload) -> dict:
    api_key = (payload.openai_api_key or "").strip()
    if _is_masked_or_placeholder(api_key):
        saved = load_llm_config().get("openai_api_key", "")
        if not saved:
            return {"ok": False, "message": "Chave API OpenAI não configurada.", "models": None}
        api_key = saved

    model = (payload.openai_model or load_llm_config().get("openai_model") or "").strip()
    if not model:
        model = "gpt-4o-mini"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return {"ok": True, "message": "Conexão com OpenAI bem-sucedida.", "models": None}
    except Exception as exc:
        msg = str(exc)
        if "401" in msg or "Incorrect API key" in msg:
            return {"ok": False, "message": "Chave API inválida.", "models": None}
        return {"ok": False, "message": f"Erro: {msg[:120]}", "models": None}
