from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def save_tokens(path: Path, tokens: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(tokens, indent=2)
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_tokens(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Token-Datei fehlt: {path}. Zuerst: portfolio-checker etrade authorize"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    ot = raw.get("oauth_token")
    os_ = raw.get("oauth_token_secret")
    if not isinstance(ot, str) or not isinstance(os_, str):
        raise ValueError("Token-Datei muss oauth_token und oauth_token_secret enthalten.")
    return {"oauth_token": ot, "oauth_token_secret": os_}
