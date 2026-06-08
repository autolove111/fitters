"""OpenAI 兼容 Embedding 适配器，支持 OpenAI、Azure、HuggingFace、LM Studio 等。"""

import json
import logging
from typing import Any, Dict

import httpx

from aidlearning.services.llm.openai_http_client import disable_ssl_verify_enabled

from .base import (
    BaseEmbeddingAdapter,
    EmbeddingProviderError,
    EmbeddingRequest,
    EmbeddingResponse,
    looks_like_multimodal_embedding_model,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleEmbeddingAdapter(BaseEmbeddingAdapter):
    NO_KEY_SENTINEL = "sk-no-key-required"

    MODELS_INFO = {
        "text-embedding-3-large": {"default": 3072, "dimensions": [256, 512, 1024, 3072]},
        "text-embedding-3-small": {"default": 1536, "dimensions": [512, 1536]},
        "text-embedding-ada-002": 1536,
    }

    def _auth_api_key(self) -> str:
        """返回真实的 API 密钥，过滤本地 Provider 的占位密钥。"""
        key = str(self.api_key or "").strip()
        if key == self.NO_KEY_SENTINEL:
            return ""
        return key

    @staticmethod
    def _extract_embeddings_from_response(data: Any) -> list[list[float]]:
        """
        从不同的 OpenAI 兼容响应 Schema 中提取嵌入。

        支持的格式包括：
        - {"data": [{"embedding": [...]}, ...]}
        - {"embeddings": [[...], ...]}
        - {"embedding": [...]}  （Ollama /api/embeddings）
        - {"result": {"data": [{"embedding": [...]}, ...]}}
        - {"output": {"embeddings": [[...], ...]}}
        """
        if not isinstance(data, dict):
            raise ValueError(f"Embedding response is not a JSON object: type={type(data).__name__}")

        # 某些 Provider 返回 HTTP 200 但载荷中包含 {"error": ...}。
        if "error" in data:
            err = data.get("error")
            if isinstance(err, dict):
                msg = (
                    err.get("message")
                    or err.get("msg")
                    or err.get("detail")
                    or json.dumps(err, ensure_ascii=False)
                )
                code = err.get("code")
                etype = err.get("type")
                raise ValueError(
                    f"Embedding provider returned error payload: "
                    f"message={msg}, code={code}, type={etype}"
                )
            raise ValueError(f"Embedding provider returned error payload: {err}")

        candidates = []
        # Standard OpenAI schema
        if isinstance(data.get("data"), list):
            candidates.append(data["data"])
        # Common proxy schema
        if isinstance(data.get("embeddings"), list):
            candidates.append(data["embeddings"])
        # Ollama /api/embeddings returns singular "embedding" as a flat vector
        if isinstance(data.get("embedding"), list):
            emb = data["embedding"]
            if emb and isinstance(emb[0], (int, float)):
                candidates.append([emb])
            else:
                candidates.append(emb)
        # Nested result/output variants
        result = data.get("result")
        if isinstance(result, dict):
            if isinstance(result.get("data"), list):
                candidates.append(result["data"])
            if isinstance(result.get("embeddings"), list):
                candidates.append(result["embeddings"])
        output = data.get("output")
        if isinstance(output, dict):
            if isinstance(output.get("data"), list):
                candidates.append(output["data"])
            if isinstance(output.get("embeddings"), list):
                candidates.append(output["embeddings"])

        for c in candidates:
            if not c:
                continue
            first = c[0]
            # list of {"embedding":[...]}
            if isinstance(first, dict) and "embedding" in first:
                return [item.get("embedding") or [] for item in c if isinstance(item, dict)]
            # list of vectors [[...], ...]
            if isinstance(first, list):
                return [item for item in c if isinstance(item, list)]

        keys = sorted(list(data.keys()))
        raise ValueError(
            "Cannot parse embeddings from response JSON. "
            f"Top-level keys={keys}, expected one of: data/embedding/embeddings/result/output."
        )

    _MAX_RETRIES = 5
    _RETRY_BACKOFF = 1.0
    _RATE_LIMIT_BACKOFF = 5.0

    def _should_send_dimensions(self, model_name: str | None) -> bool:
        """决定是否在请求载荷中附加 `dimensions`。

        由 `self.send_dimensions` 驱动的三态语义：
        * ``True``  -> 始终发送（用户显式选择启用）
        * ``False`` -> 从不发送（用户显式选择禁用）
        * ``None``  -> 自动：对已知接受 OpenAI 风格 ``dimensions`` 参数的
          模型系列发送 — OpenAI ``text-embedding-3*``、
          Qwen3-Embedding、Qwen3-VL-Embedding。
        """
        if self.send_dimensions is True:
            return True
        if self.send_dimensions is False:
            return False
        if not model_name:
            return False
        lname = model_name.lower()
        if lname.startswith("text-embedding-3"):
            return True
        if "qwen3-embedding" in lname or "qwen3-vl-embedding" in lname:
            return True
        return False

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        import asyncio

        headers = {"Content-Type": "application/json"}
        api_key = self._auth_api_key()
        if self.api_version:
            if api_key:
                headers["api-key"] = api_key
        elif api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update({str(k): str(v) for k, v in self.extra_headers.items()})

        # 多模态：仅对明确支持图片/视觉嵌入的模型名称将 `contents` 作为 `input` 传递。
        # 这防止因 Provider 系列中存在某些多模态模型而导致图片索引意外命中普通文本嵌入模型。
        model = request.model or self.model
        if request.contents and not looks_like_multimodal_embedding_model(model):
            raise ValueError(
                f"OpenAI-compatible embedding model '{model}' does not support "
                "multimodal `contents`."
            )
        input_payload: Any = request.contents if request.contents else request.texts

        payload = {
            "input": input_payload,
            "model": model,
            "encoding_format": request.encoding_format or "float",
        }

        # `dimensions` 为可选启用。用户的 `send_dimensions` 标志在显式设置时（True/False）优先；
        # 否则回退到模型系列启发式，因为只有 OpenAI 的 text-embedding-3* 系列官方支持此参数
        # — 其他 Provider（如通过 litellm 网关的 Qwen text-embedding-v4）会返回 HTTP 400。
        dim_value = request.dimensions or self.dimensions
        if dim_value and self._should_send_dimensions(model):
            payload["dimensions"] = dim_value

        # URL 透明：直接请求 `base_url`。Azure 的 `?api-version=...`
        # 是查询参数（非路径组件），因此仍然追加。
        url = self.base_url
        if self.api_version:
            if "?" not in url:
                url += f"?api-version={self.api_version}"
            else:
                url += f"&api-version={self.api_version}"

        logger.debug(f"Sending embedding request to {url} with {len(request.texts)} texts")

        timeout = httpx.Timeout(
            connect=10.0,
            read=max(self.request_timeout, 60),
            write=10.0,
            pool=10.0,
        )
        last_exc: Exception | None = None
        for attempt in range(1 + self._MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=timeout, verify=not disable_ssl_verify_enabled()
                ) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    # 处理限流（429）并重试
                    if response.status_code == 429:
                        retry_after = float(response.headers.get("Retry-After", 0))
                        wait = max(retry_after, self._RATE_LIMIT_BACKOFF * (2**attempt))
                        logger.warning(
                            f"Rate limited (429) on attempt {attempt + 1}/{1 + self._MAX_RETRIES}, "
                            f"retrying in {wait:.1f}s..."
                        )
                        await asyncio.sleep(wait)
                        last_exc = Exception("HTTP 429 Too Many Requests")
                        continue

                    if response.status_code >= 400:
                        body_text = response.text
                        logger.error(f"HTTP {response.status_code} from {url}: {body_text[:2000]}")
                        raise EmbeddingProviderError(
                            f"Embedding provider returned HTTP {response.status_code}",
                            status=response.status_code,
                            body=body_text,
                            model=model,
                            url=url,
                            provider="openai_compat",
                        )

                    # 2xx 响应但非 JSON 主体通常意味着端点/模型配对错误，
                    # 或网关将请求路由到了 HTML 页面。将其作为结构化诊断信息输出。
                    try:
                        data = response.json()
                    except (json.JSONDecodeError, ValueError) as exc:
                        body_text = response.text
                        content_type = response.headers.get("content-type", "")
                        body_preview = body_text.strip()[:200] or "<empty body>"
                        hint = ""
                        if not body_text.strip():
                            hint = (
                                " 响应主体为空 — 该端点可能不支持嵌入，"
                                "或所选模型可能不是嵌入模型。"
                            )
                        elif (
                            "text/html" in content_type.lower()
                            or body_preview.lstrip().startswith("<")
                        ):
                            hint = (
                                " 响应为 HTML 而非 JSON — URL 可能有误，"
                                "或网关未暴露 `/v1/embeddings`。"
                            )
                        raise EmbeddingProviderError(
                            (
                                f"Embedding provider returned non-JSON response "
                                f"(content-type={content_type!r}): {exc}.{hint}"
                            ),
                            status=response.status_code,
                            body=body_text,
                            model=model,
                            url=url,
                            provider="openai_compat",
                        ) from exc
                break
            except httpx.TransportError as exc:
                # httpx.TransportError 涵盖所有瞬态传输层故障：
                # ConnectError、ReadError、WriteError、ConnectTimeout、
                # ReadTimeout、WriteTimeout、PoolTimeout、RemoteProtocolError 等。
                # 对这些错误进行退避重试是安全的，无需不断扩展显式白名单。
                last_exc = exc
                if attempt < self._MAX_RETRIES:
                    wait = self._RETRY_BACKOFF * (2**attempt)
                    logger.warning(
                        f"Embedding request transport error ({type(exc).__name__}: {exc}) "
                        f"on attempt {attempt + 1}/{1 + self._MAX_RETRIES}, "
                        f"retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        f"Embedding request failed after {1 + self._MAX_RETRIES} attempts "
                        f"({type(exc).__name__}: {exc})"
                    )
                    raise
        else:
            if last_exc:
                raise last_exc

        embeddings = self._extract_embeddings_from_response(data)
        if not embeddings:
            raise ValueError("Embedding response parsed successfully but no vectors were found.")

        actual_dims = len(embeddings[0]) if embeddings else 0
        expected_dims = request.dimensions or self.dimensions
        model_name = data.get("model") if isinstance(data, dict) else None
        if not model_name:
            model_name = model

        if expected_dims and actual_dims != expected_dims:
            logger.warning(
                f"Dimension mismatch: expected {expected_dims}, got {actual_dims}. "
                f"Model '{model_name}' may not support custom dimensions."
            )

        logger.info(
            f"Successfully generated {len(embeddings)} embeddings "
            f"(model: {model_name}, dimensions: {actual_dims})"
        )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model_name,
            dimensions=actual_dims,
            usage=data.get("usage", {}) if isinstance(data, dict) else {},
        )

    def get_model_info(self) -> Dict[str, Any]:
        model_info = self.MODELS_INFO.get(self.model, self.dimensions)

        if isinstance(model_info, dict):
            return {
                "model": self.model,
                "dimensions": model_info.get("default", self.dimensions),
                "supported_dimensions": model_info.get("dimensions", []),
                "supports_variable_dimensions": len(model_info.get("dimensions", [])) > 1,
                "multimodal": looks_like_multimodal_embedding_model(self.model),
                "provider": "openai_compatible",
            }
        else:
            return {
                "model": self.model,
                "dimensions": model_info or self.dimensions,
                "supports_variable_dimensions": False,
                "multimodal": looks_like_multimodal_embedding_model(self.model),
                "provider": "openai_compatible",
            }
