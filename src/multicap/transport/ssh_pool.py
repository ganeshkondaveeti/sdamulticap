from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol, TypeVar, cast


class SshConnection(Protocol):
    def send_command(self, command: str, **kwargs: object) -> str: ...

    def disconnect(self) -> None: ...


class ConnectionFactory(Protocol):
    def __call__(self, **kwargs: object) -> SshConnection: ...


@dataclass(frozen=True, slots=True)
class SshTarget:
    host: str
    platform: str
    username: str
    password: str
    port: int = 22
    timeout_seconds: float = 20.0
    secret_name: str | None = None


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 3
    base_delay_seconds: float = 0.2
    jitter_seconds: float = 0.05


class _Gate:
    def __init__(self, permits: int) -> None:
        self._semaphore = threading.BoundedSemaphore(permits)

    def __enter__(self) -> None:
        self._semaphore.acquire()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._semaphore.release()


_T = TypeVar("_T")


@dataclass(slots=True)
class SshConnectionPool:
    connection_factory: ConnectionFactory
    platform_caps: Mapping[str, int] = field(default_factory=dict)
    default_platform_cap: int = 8
    per_host_cap: int = 1
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    sleeper: Callable[[float], None] = time.sleep
    jitter: Callable[[float, float], float] = random.uniform
    _lock: threading.Lock = field(init=False)
    _connections: dict[str, SshConnection] = field(init=False)
    _host_gates: dict[str, _Gate] = field(init=False)
    _platform_gates: dict[str, _Gate] = field(init=False)

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[str, SshConnection] = {}
        self._host_gates: dict[str, _Gate] = {}
        self._platform_gates: dict[str, _Gate] = {}

    @classmethod
    def netmiko(
        cls,
        platform_caps: Mapping[str, int] | None = None,
        default_platform_cap: int = 8,
        per_host_cap: int = 1,
        retry: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> SshConnectionPool:
        from netmiko import ConnectHandler

        def factory(**kwargs: object) -> SshConnection:
            return cast(SshConnection, ConnectHandler(**kwargs))

        return cls(
            connection_factory=factory,
            platform_caps=platform_caps or {},
            default_platform_cap=default_platform_cap,
            per_host_cap=per_host_cap,
            retry=retry or RetryPolicy(),
            sleeper=sleeper,
            jitter=jitter,
        )

    def execute(self, target: SshTarget, command: str, **kwargs: object) -> str:
        return self._with_retry(lambda: self._execute_once(target, command, **kwargs))

    def close_all(self) -> None:
        with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            connection.disconnect()

    def _execute_once(self, target: SshTarget, command: str, **kwargs: object) -> str:
        with (
            self._gate(self._host_gates, target.host, self.per_host_cap),
            self._gate(
                self._platform_gates,
                target.platform,
                self.platform_caps.get(target.platform, self.default_platform_cap),
            ),
        ):
            try:
                connection = self._connection(target)
                return connection.send_command(command, **kwargs)
            except Exception:
                self._drop_connection(target.host)
                raise

    def _connection(self, target: SshTarget) -> SshConnection:
        with self._lock:
            connection = self._connections.get(target.host)
            if connection is None:
                connection = self.connection_factory(
                    device_type=target.platform,
                    host=target.host,
                    username=target.username,
                    password=target.password,
                    port=target.port,
                    timeout=target.timeout_seconds,
                )
                self._connections[target.host] = connection
            return connection

    def _drop_connection(self, host: str) -> None:
        with self._lock:
            connection = self._connections.pop(host, None)
        if connection is not None:
            connection.disconnect()

    def _gate(self, gates: dict[str, _Gate], key: str, permits: int) -> _Gate:
        with self._lock:
            gate = gates.get(key)
            if gate is None:
                gate = _Gate(permits)
                gates[key] = gate
            return gate

    def _with_retry(self, call: Callable[[], _T]) -> _T:
        last_error: Exception | None = None
        for attempt in range(self.retry.attempts):
            try:
                return call()
            except Exception as error:
                last_error = error
                if attempt + 1 == self.retry.attempts:
                    break
                delay = self.retry.base_delay_seconds * (2**attempt)
                delay += self.jitter(0.0, self.retry.jitter_seconds)
                self.sleeper(delay)
        if last_error is None:
            raise RuntimeError("SSH retry policy has no attempts")
        raise last_error
