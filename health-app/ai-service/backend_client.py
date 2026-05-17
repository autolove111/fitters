import os
from typing import Any

import requests


class BackendClient:
    def __init__(self, authorization: str):
        self.base_url = os.getenv("BACKEND_INTERNAL_URL", "http://health-backend:8080").rstrip("/")
        self.headers = {"Authorization": authorization}

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = requests.get(
            f"{self.base_url}{path}",
            headers=self.headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", payload)
