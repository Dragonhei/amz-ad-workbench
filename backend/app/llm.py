"""大模型接入：OpenAI 兼容协议，指数退避重试、JSON 强约束、失败降级。"""
import base64
import json
import re
import time

import httpx

MAX_RETRIES = 3
TIMEOUT = 90


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


_SECRET = b"amz-ad-workbench"


def encrypt_key(plain: str) -> str:
    if not plain:
        return ""
    return base64.b64encode(_xor(plain.encode(), _SECRET)).decode()


def decrypt_key(enc: str) -> str:
    if not enc:
        return ""
    try:
        return _xor(base64.b64decode(enc), _SECRET).decode(errors="ignore")
    except Exception:
        return ""


def mask_key(enc: str) -> str:
    k = decrypt_key(enc)
    if not k:
        return ""
    return (k[:6] + "****" + k[-4:]) if len(k) > 12 else "****"


def _extract_json(text: str):
    """从模型输出中稳健提取 JSON。"""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def call_llm(provider, system_prompt: str, user_prompt: str):
    """返回 (data, usage, error)。data 为 {"items": [...]} 或 None。"""
    api_key = decrypt_key(provider.api_key_enc or "")
    if not api_key:
        return None, {}, {"code": "no_key", "message": "未配置 API Key，已自动降级到内置规则引擎"}
    try:
        params = json.loads(provider.params_json or "{}")
    except json.JSONDecodeError:
        params = {}
    payload = {
        "model": provider.model,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_prompt}],
        "temperature": params.get("temperature", 0.2),
        "max_tokens": params.get("max_tokens", 4000),
    }
    if params.get("response_json", True):
        payload["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_err = {"code": "failed", "message": "调用失败"}
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=TIMEOUT) as cli:
                resp = cli.post(provider.endpoint, headers=headers, json=payload)
            if resp.status_code in (401, 403):
                return None, {}, {"code": "auth", "message": f"鉴权失败({resp.status_code})，请检查 API Key 与 Endpoint"}
            if resp.status_code == 429 or resp.status_code >= 500:
                last_err = {"code": "retryable",
                            "message": f"服务端返回 {resp.status_code}，已重试 {attempt + 1} 次"}
                time.sleep(2 ** attempt)
                continue
            if resp.status_code >= 400:
                return None, {}, {"code": "client", "message": f"请求错误 {resp.status_code}: {resp.text[:200]}"}
            body = resp.json()
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = body.get("usage", {}) or {}
            data = _extract_json(content)
            if not data or "items" not in data:
                last_err = {"code": "parse", "message": "模型输出不是合法 JSON，尝试修复中"}
                time.sleep(1)
                continue
            return data, usage, None
        except httpx.TimeoutException:
            last_err = {"code": "timeout", "message": f"请求超时（{TIMEOUT}s），已重试 {attempt + 1} 次"}
            time.sleep(2 ** attempt)
        except Exception as e:                                  # noqa: BLE001
            last_err = {"code": "exception", "message": f"{type(e).__name__}: {str(e)[:200]}"}
            time.sleep(2 ** attempt)
    return None, {}, last_err


DIMENSION_ZH = {d["code"]: d["name_zh"] for d in
                [{"code": "budget", "name_zh": "预算分配"}, {"code": "bid", "name_zh": "竞价调整"},
                 {"code": "keyword_add", "name_zh": "关键词增删"}, {"code": "negative", "name_zh": "否定词"},
                 {"code": "placement", "name_zh": "广告位"}, {"code": "structure", "name_zh": "投放结构"},
                 {"code": "listing", "name_zh": "Listing 优化"}, {"code": "inventory", "name_zh": "库存联动"},
                 {"code": "schedule", "name_zh": "节奏排期"}, {"code": "competitor", "name_zh": "竞品应对"},
                 {"code": "risk", "name_zh": "风险预警"}, {"code": "review", "name_zh": "效果复盘"}]}
ZH_TO_CODE = {v: k for k, v in DIMENSION_ZH.items()}


def normalize_items(data: dict):
    """把模型输出规整为内部 12 维结构，过滤无法归类的条目。"""
    out = []
    for it in (data or {}).get("items", []):
        dim = it.get("dimension", "")
        code = dim if dim in DIMENSION_ZH else ZH_TO_CODE.get(dim)
        if not code:
            continue
        out.append({
            "dimension": code,
            "title": str(it.get("title", ""))[:300] or "未命名建议",
            "detail": str(it.get("detail", "")),
            "action": str(it.get("action", "")),
            "expected_impact": str(it.get("expected_impact", "")),
            "priority": it.get("priority", "P2") if it.get("priority") in ("P0", "P1", "P2") else "P2",
            "confidence": max(0.0, min(1.0, float(it.get("confidence", 0.6) or 0.6))),
            "evidence": it.get("evidence", []) if isinstance(it.get("evidence"), list) else [],
        })
    return out
