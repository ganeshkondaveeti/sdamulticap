from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast


class NetconfSession(Protocol):
    def get(self, filter: object | None = None) -> object: ...

    def close_session(self) -> None: ...


NetconfFactory = Callable[..., NetconfSession]


@dataclass(frozen=True, slots=True)
class NetconfEndpoint:
    host: str
    username: str
    password: str
    port: int = 830
    timeout_seconds: float = 10.0


@dataclass(slots=True)
class NetconfClient:
    endpoint: NetconfEndpoint
    factory: NetconfFactory | None = None

    def get(self, filter_spec: object | None = None) -> object:
        session = self._factory()(
            host=self.endpoint.host,
            port=self.endpoint.port,
            username=self.endpoint.username,
            password=self.endpoint.password,
            hostkey_verify=False,
            timeout=self.endpoint.timeout_seconds,
        )
        try:
            return session.get(filter=filter_spec)
        finally:
            session.close_session()

    def _factory(self) -> NetconfFactory:
        if self.factory is not None:
            return self.factory
        from ncclient import manager

        return cast(NetconfFactory, manager.connect)
