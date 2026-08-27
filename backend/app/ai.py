from __future__ import annotations

import json
from typing import Any

import httpx


class AiConfigError(RuntimeError):
    pass


def _endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def chat_completion(config: dict[str, str], messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
    if not config.get("api_key") or not config.get("base_url") or not config.get("model_name"):
        raise AiConfigError("请先在设置中配置 API Key、Base URL 和模型名称。")
    payload: dict[str, Any] = {"model": config["model_name"], "messages": messages, "temperature": 0.3}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        response = httpx.post(
            _endpoint(config["base_url"]),
            headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"]
    except httpx.HTTPError as exc:
        raise RuntimeError(f"模型服务请求失败：{exc}") from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("模型返回格式无法识别。") from exc


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError("模型没有返回有效的结构化结果。") from exc
    if not isinstance(value, dict):
        raise RuntimeError("模型返回结果不是对象。")
    return value
