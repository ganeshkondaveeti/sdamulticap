from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RestconfEndpoint:
    base_url: str
    username: str
    password: str
    verify_tls: bool = True
    timeout_seconds: float = 10.0


@dataclass(slots=True)
class RestconfClient:
    endpoint: RestconfEndpoint

    def get_json(self, path: str) -> object:
        import httpx

        url = f"{self.endpoint.base_url.rstrip('/')}/{path.lstrip('/')}"
        response = httpx.get(
            url,
            auth=(self.endpoint.username, self.endpoint.password),
            headers={"Accept": "application/yang-data+json, application/json"},
            timeout=self.endpoint.timeout_seconds,
            verify=self.endpoint.verify_tls,
        )
        response.raise_for_status()
        return response.json()
