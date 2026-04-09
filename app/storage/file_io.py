from __future__ import annotations

import json
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any


def model_to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value


def ensure_json_file(path: Path, default: Any) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, default)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    with path.open("r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}") from exc


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(serialized)
            file.flush()
            os.fsync(file.fileno())
        replaced = False
        for _ in range(3):
            try:
                os.replace(temp_path, path)
                replaced = True
                break
            except PermissionError:
                time.sleep(0.05)
        if not replaced:
            # 某些 Windows 环境下替换临时文件会被拦截，回退到直接写目标文件。
            path.write_text(serialized, encoding="utf-8")
    finally:
        if os.path.exists(temp_path):
            for _ in range(3):
                try:
                    os.remove(temp_path)
                    break
                except PermissionError:
                    time.sleep(0.05)
