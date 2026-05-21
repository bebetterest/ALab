from __future__ import annotations

import base64
import re

import pytest

from alab import ids as ids_module
from alab.errors import AlabError
from alab.ids import new_id, random_suffix, require_complete_id, slugify


def test_random_suffix_is_unpadded_base64url_128_bits(monkeypatch) -> None:
    entropy = bytes(range(16))
    monkeypatch.setattr(ids_module.secrets, "token_bytes", lambda n: entropy if n == 16 else b"")

    suffix = random_suffix()

    assert suffix == "AAECAwQFBgcICQoLDA0ODw"
    assert len(suffix) == 22
    assert "=" not in suffix
    assert re.fullmatch(r"[A-Za-z0-9_-]{22}", suffix)
    assert base64.urlsafe_b64decode(suffix + "==") == entropy


def test_new_id_and_complete_id_validation(monkeypatch) -> None:
    monkeypatch.setattr(ids_module, "random_suffix", lambda: "A" * 22)

    object_id = new_id("exp", "Attempt One")

    assert object_id == "exp-attempt-one-" + "A" * 22
    assert require_complete_id(object_id, "exp") == object_id


@pytest.mark.parametrize(
    "value",
    [
        "exp-attempt-one",
        "exp-attempt-one-" + "A" * 21,
        "exp-attempt-one-" + "A" * 23,
        "exp-attempt-one-" + "A" * 21 + "=",
    ],
)
def test_require_complete_id_rejects_non_v1_suffixes(value: str) -> None:
    with pytest.raises(AlabError) as excinfo:
        require_complete_id(value, "exp")

    assert excinfo.value.code == "CONFIG_INVALID"
    assert "object ids must be complete" in excinfo.value.reason


def test_slugify_normalizes_names_and_uses_fallback() -> None:
    assert slugify("ＡLab Experiment!", "fallback") == "alab-experiment"
    assert slugify("!!!", "fallback") == "fallback"
