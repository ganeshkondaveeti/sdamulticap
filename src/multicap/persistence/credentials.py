from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CredentialRef:
    service: str
    username: str


@dataclass(slots=True)
class CredentialStore:
    service_prefix: str = "multicap"

    def store(self, name: str, username: str, password: str) -> CredentialRef:
        import keyring

        service = self._service(name)
        keyring.set_password(service, username, password)
        return CredentialRef(service=service, username=username)

    def retrieve(self, ref: CredentialRef) -> str:
        import keyring

        password = keyring.get_password(ref.service, ref.username)
        if password is None:
            raise KeyError(f"credential not found: {ref.service}/{ref.username}")
        return str(password)

    def delete(self, ref: CredentialRef) -> None:
        import keyring

        keyring.delete_password(ref.service, ref.username)

    def _service(self, name: str) -> str:
        return f"{self.service_prefix}.{name}"
