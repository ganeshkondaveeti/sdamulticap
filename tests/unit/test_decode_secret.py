from __future__ import annotations

import base64

import pytest

from multicap.release_tools import decode_secret


@pytest.mark.unit
def test_decode_secret_accepts_wrapped_base64() -> None:
    encoded = base64.b64encode(b"certificate-bytes").decode()

    assert decode_secret(f" {encoded[:6]}\n{encoded[6:]} ", allow_raw=False) == b"certificate-bytes"


@pytest.mark.unit
def test_decode_secret_accepts_raw_armored_key_when_allowed() -> None:
    raw = "-----BEGIN PGP PRIVATE KEY BLOCK-----\nabc\n-----END PGP PRIVATE KEY BLOCK-----"

    assert decode_secret(raw, allow_raw=True) == raw.encode()


@pytest.mark.unit
def test_decode_secret_rejects_raw_text_by_default() -> None:
    with pytest.raises(SystemExit, match="not valid base64"):
        _ = decode_secret("not a base64 certificate", allow_raw=False)
