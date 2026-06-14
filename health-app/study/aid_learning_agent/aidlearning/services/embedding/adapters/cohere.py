"""Cohere Embedding 适配器，支持 v1 和 v2 API。"""

import logging
from typing import Any, Dict

import httpx

from aidlearning.services.llm.openai_http_client import disable_ssl_verify_enabled

from .base import BaseEmbeddingAdapter, EmbeddingRequest, EmbeddingResponse

logger = logging.getLogger(__name__)


class CohereEmbeddingAdapter(BaseEmbeddingAdapter):
    """Cohere Embed API 适配器（v1 和 v2）。"""

    MODELS_INFO = {
        "embed-v4.0": {
            "dimensions": [256, 512, 1024, 1536],
            "default": 1024,
            "api_version": "v2",
            "multimodal": True,
        },
        "embed-english-v3.0": {
            "dimensions": [1024],
            "default": 1024,
            "api_version": "v1",
            "multimodal": False,
        },
        "embed-multilingual-v3.0": {
            "dimensions": [1024],
            "default": 1024,
            "api_version": "v1",
            "multimodal": False,
        },
        "embed-multilingual-light-v3.0": {
            "dimensions": [384],
            "default": 384,
            "api_version": "v1",
            "multimodal": False,
        },
        "embed-english-light-v3.0": {
            "dimensions": [384],
            "default": 384,
            "api_version": "v1",
            "multimodal": False,
        },
    }

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update({str(k): str(v) for k, v in self.extra_headers.items()})

        model_name = request.model or self.model
        model_info = self.MODELS_INFO.get(model_name, {})
        # `api_version` 现在纯粹是请求格式选择器（v1 vs v2 载荷）。
        # URL 本身为用户配置的值。解析顺序：
        #   显式 self.api_version（目录/环境覆盖）→ MODELS_INFO 条目 → "v2"
        api_version = self.api_version or model_info.get("api_version") or "v2"
        dimension = request.dimensions or self.dimensions

        input_type = request.input_type or "search_document"

        if api_version == "v1":
            if request.contents:
                raise ValueError(
                    "Cohere v1 API does not support multimodal `contents`. "
                    "Use embed-v4.0 (v2 API) for multimodal."
                )
            payload = {
                "texts": request.texts,
                "model": model_name,
                "input_type": input_type,
            }

            if not request.truncate:
                payload["truncate"] = "NONE"
        else:
            if request.contents and not bool(model_info.get("multimodal", False)):
                raise ValueError(
                    f"Cohere model '{model_name}' does not support multimodal `contents`."
                )
            payload = {
                "model": model_name,
                "embedding_types": ["float"],
                "input_type": input_type,
            }

            if request.contents:
                # Cohere v2 多模态：`inputs: [{content: [{type, text|image_url}]}]`
                # 我们将简单的 [{text|image|video}] 契约转换为 v2 的嵌套格式。
                # v2 无法在一个输入中混合文本+图片，因此每个内容字典成为独立的输入项。
                inputs = []
                for item in request.contents:
                    if not isinstance(item, dict):
                        continue
                    kind, value = next(iter(item.items()))
                    if kind == "text":
                        inputs.append({"content": [{"type": "text", "text": value}]})
                    elif kind == "image":
                        inputs.append(
                            {"content": [{"type": "image_url", "image_url": {"url": value}}]}
                        )
                    else:
                        raise ValueError(f"Cohere v2 does not support content type '{kind}'")
                payload["inputs"] = inputs
            else:
                payload["texts"] = request.texts

            supported_dims = model_info.get("dimensions", [])
            if isinstance(supported_dims, list) and len(supported_dims) > 1:
                payload["output_dimension"] = dimension or model_info.get("default")

            if not request.truncate:
                payload["truncate"] = "NONE"

        url = self.base_url

        logger.debug(f"Sending embedding request to {url} with {len(request.texts)} texts")

        async with httpx.AsyncClient(
            timeout=self.request_timeout, verify=not disable_ssl_verify_enabled()
        ) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code >= 400:
                logger.error(f"HTTP {response.status_code} response body: {response.text}")

            response.raise_for_status()
            data = response.json()

        if api_version == "v1":
            embeddings = data["embeddings"]
        else:
            embeddings = data["embeddings"]["float"]

        actual_dims = len(embeddings[0]) if embeddings else 0
        expected_dims = request.dimensions or self.dimensions

        if expected_dims and actual_dims != expected_dims:
            logger.warning(f"Dimension mismatch: expected {expected_dims}, got {actual_dims}")

        logger.info(
            f"Successfully generated {len(embeddings)} embeddings "
            f"(model: {data.get('model', self.model)}, dimensions: {actual_dims})"
        )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=data.get("model", self.model),
            dimensions=actual_dims,
            usage=data.get("meta", {}).get("billed_units", {}),
        )

    def get_model_info(self) -> Dict[str, Any]:
        model_info = self.MODELS_INFO.get(self.model, {})
        dimensions_list = model_info.get("dimensions", [])
        api_version = self.api_version or model_info.get("api_version") or "v2"
        return {
            "model": self.model,
            "dimensions": model_info.get("default", self.dimensions),
            "supports_variable_dimensions": len(dimensions_list) > 1
            if isinstance(dimensions_list, list)
            else False,
            "multimodal": bool(model_info.get("multimodal", False)) and api_version != "v1",
            "provider": "cohere",
        }
