"""Local development LLM configuration and server-side prompt routing."""
import json
import os
from pathlib import Path
from threading import Lock

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, SecretStr, field_validator

router = APIRouter(prefix="/api", tags=["LLM"])
settings_dir = Path(os.getenv("LLM_SETTINGS_DIR", "/data/llm"))
settings_lock = Lock()
OPENAI_URL = "https://api.openai.com/v1"


class ConnectionSettings(BaseModel):
    base_url: str = Field(default="https://api.openai.com/v1", max_length=2048)
    model: str = Field(default="", max_length=200)
    api_key: SecretStr | None = None
    system_prompt: str = Field(default="", max_length=32000)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value):
        value = value.strip().rstrip("/")
        if value != OPENAI_URL:
            raise ValueError("Only the OpenAI API is supported.")
        return value

    @field_validator("model")
    @classmethod
    def validate_model(cls, value):
        return value.strip()


class Prompt(BaseModel):
    prompt: str = Field(min_length=1, max_length=32000)


def read_settings():
    path = settings_dir / "connection.json"
    settings = json.loads(path.read_text()) if path.exists() else {}
    # Do not reuse another provider's credentials or model after the switch.
    if settings.get("base_url") != OPENAI_URL:
        settings.update(base_url=OPENAI_URL, model="", encrypted_key="")
    return settings


def cipher():
    settings_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = settings_dir / "encryption.key"
    if not path.exists():
        with path.open("xb") as handle:
            os.chmod(path, 0o600)
            handle.write(Fernet.generate_key())
    return Fernet(path.read_bytes())


def public_settings(settings):
    return {
        "base_url": settings.get("base_url", "https://api.openai.com/v1"),
        "model": settings.get("model", ""),
        "has_api_key": bool(settings.get("encrypted_key")),
        "system_prompt": settings.get("system_prompt", ""),
    }


@router.get("/settings/llm")
def get_settings(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return public_settings(read_settings())


@router.get("/settings/llm/models")
async def list_models(response: Response):
    response.headers["Cache-Control"] = "no-store"
    settings = read_settings()
    if not settings.get("encrypted_key"):
        raise HTTPException(409, "Save your OpenAI API key first, then refresh the model list.")
    key = cipher().decrypt(settings["encrypted_key"].encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
            result = await client.get(OPENAI_URL + "/models", headers={"Authorization": f"Bearer {key}"})
    except httpx.RequestError:
        raise HTTPException(502, "Could not load OpenAI models. Please try again.") from None
    if result.status_code in (401, 403):
        raise HTTPException(502, "OpenAI could not list models with this key. Check the key and its permissions.")
    if not result.is_success:
        raise HTTPException(502, "Could not load OpenAI models. Please try again later.")
    try:
        models = result.json()["data"]
        if not isinstance(models, list):
            raise ValueError()
        # The models API has no endpoint-capability field. Show text-model
        # families, excluding known specialized variants; connection testing
        # remains the final check of Chat Completions compatibility.
        ids = sorted({item["id"] for item in models if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item["id"].startswith(("gpt-", "chatgpt-", "chat-", "o1", "o3", "o4", "ft:gpt-"))
            and not any(part in item["id"] for part in ("audio", "realtime", "transcribe", "tts", "image", "search", "deep-research", "codex", "instruct"))
            and "pro" not in item["id"].split("-")})
    except (ValueError, KeyError, TypeError):
        raise HTTPException(502, "OpenAI returned an unreadable model list.") from None
    return {"models": ids}


@router.put("/settings/llm")
def save_settings(payload: ConnectionSettings):
    with settings_lock:
        previous = read_settings()
        key = payload.api_key.get_secret_value().strip() if payload.api_key else ""
        if key and (len(key) > 8192 or any(character.isspace() for character in key)):
            raise HTTPException(400, "API key must not contain whitespace and must be at most 8192 characters.")
        base_url = OPENAI_URL
        model = payload.model if "model" in payload.model_fields_set else previous.get("model", "")
        # Never reuse a saved credential at a different destination.
        encrypted = cipher().encrypt(key.encode()).decode() if key else (
            previous.get("encrypted_key", "") if previous.get("base_url") == base_url else ""
        )
        settings = {"base_url": base_url, "model": model, "encrypted_key": encrypted}
        settings_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        for field in ("system_prompt",):
            settings[field] = getattr(payload, field) if field in payload.model_fields_set else previous.get(field, "")
        temporary = settings_dir / "connection.tmp"
        with temporary.open("w") as handle:
            os.chmod(temporary, 0o600)
            json.dump(settings, handle)
        temporary.replace(settings_dir / "connection.json")
    return public_settings(settings)


@router.delete("/settings/llm")
def disconnect():
    with settings_lock:
        (settings_dir / "connection.json").unlink(missing_ok=True)
    return {"message": "Connection removed."}


async def request_completion(prompt):
    settings = read_settings()
    if not all(settings.get(field) for field in ("base_url", "model", "encrypted_key")):
        raise HTTPException(409, "Add an OpenAI model and API key in Settings before sending a request.")
    key = cipher().decrypt(settings["encrypted_key"].encode()).decode()
    instructions = []
    if settings.get("system_prompt", "").strip():
        instructions.append(settings["system_prompt"])
    messages = [{"role": "system", "content": "\n\n".join(instructions)}] if instructions else []
    messages.append({"role": "user", "content": prompt})
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=False, trust_env=False) as client:
            response = await client.post(
                OPENAI_URL + "/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": settings["model"], "messages": messages},
            )
    except httpx.TimeoutException:
        raise HTTPException(504, "OpenAI timed out. Please try again.") from None
    except httpx.RequestError:
        raise HTTPException(502, "Could not reach OpenAI. Please try again.") from None
    if response.status_code in (401, 403):
        raise HTTPException(502, "OpenAI rejected the API key or model access.")
    if response.status_code == 429:
        raise HTTPException(502, "OpenAI reported a rate or quota limit.")
    if not response.is_success:
        raise HTTPException(502, f"OpenAI returned HTTP {response.status_code}. Check the OpenAI model ID.")
    try:
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError()
    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(502, "OpenAI did not return a text response in the expected format.") from None
    return {"text": content, "model": settings["model"]}


@router.post("/settings/llm/test")
async def test_connection():
    await request_completion("Reply with the single word Connected.")
    return {"message": "Connected. The configured model responded successfully."}


@router.post("/llm/prompt")
async def send_prompt(payload: Prompt):
    if not payload.prompt.strip():
        raise HTTPException(400, "Enter a prompt.")
    return await request_completion(payload.prompt)
