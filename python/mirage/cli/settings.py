# ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from mirage.cli.env import ENV_DAEMON_URL, ENV_TOKEN
from mirage.server.auth import storage as auth_storage
from mirage.server.daemon_config import read_daemon_table
from mirage.server.paths import mirage_home

DEFAULT_DAEMON_URL = "http://127.0.0.1:8765"


@dataclass
class DaemonSettings:
    url: str = DEFAULT_DAEMON_URL
    socket: str = ""
    auth_token: str = ""
    idle_grace_seconds: float = 30.0


def config_path() -> Path:
    return mirage_home() / "config.toml"


def load_daemon_settings(path: Path | None = None) -> DaemonSettings:
    """Load daemon settings, applying the override chain.

    Order of precedence (highest first):
        1. ``MIRAGE_DAEMON_URL`` env var
        2. ``MIRAGE_TOKEN`` env var
        3. values in ``$MIRAGE_HOME/config.toml`` (default
           ``~/.mirage/config.toml``) ``[daemon]`` table
        4. defaults

    Args:
        path (Path | None): config file location. Defaults to
            ``config_path()``.

    Returns:
        DaemonSettings: resolved settings.
    """
    use_path = path or config_path()
    if path is not None:
        with open(use_path, "rb") as f:
            table = tomllib.load(f).get("daemon", {})
    else:
        table = read_daemon_table(mirage_home())
    settings = DaemonSettings(
        url=str(table.get("url", DEFAULT_DAEMON_URL)),
        socket=str(table.get("socket", "")),
        auth_token=str(table.get("auth_token", "")),
        idle_grace_seconds=float(table.get("idle_grace_seconds", 30.0)),
    )
    env_url = os.environ.get(ENV_DAEMON_URL)
    if env_url:
        settings.url = env_url
    env_token = os.environ.get(ENV_TOKEN)
    if env_token:
        settings.auth_token = env_token
    if not settings.auth_token:
        file_token = auth_storage.read_token_file(
            auth_storage.default_token_file())
        if file_token:
            settings.auth_token = file_token
    return settings


ALLOWED_KEYS = frozenset({
    "url",
    "socket",
    "auth_token",
    "idle_grace_seconds",
    "pid_file",
    "version_root",
    "snapshot_root",
})
_NUMERIC_KEYS = frozenset({"idle_grace_seconds"})


def _check_key(key: str) -> None:
    if key not in ALLOWED_KEYS:
        raise KeyError(f"unknown config key: {key!r}; allowed: "
                       f"{', '.join(sorted(ALLOWED_KEYS))}")


def _format_value(key: str, value: str) -> str:
    if key in _NUMERIC_KEYS:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _config_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text().splitlines()


def list_config(path: Path | None = None) -> dict:
    """Return the ``[daemon]`` table as written in the config file.

    Args:
        path (Path | None): config file. Defaults to ``config_path()``.

    Returns:
        dict: file-level key/value strings (no env or default folding).
    """
    use_path = path or config_path()
    if not use_path.exists():
        return {}
    with open(use_path, "rb") as f:
        table = tomllib.load(f).get("daemon", {})
    return {k: str(v) for k, v in table.items()}


def get_config(key: str, path: Path | None = None) -> str | None:
    """Return one ``[daemon]`` key's file value, or ``None`` if unset.

    Args:
        key (str): a key in :data:`ALLOWED_KEYS`.
        path (Path | None): config file. Defaults to ``config_path()``.

    Returns:
        str | None: the value, or ``None`` if absent.
    """
    _check_key(key)
    return list_config(path).get(key)


def set_config(key: str, value: str, path: Path | None = None) -> None:
    """Write ``key = value`` into the ``[daemon]`` table, in place.

    Creates the file and ``[daemon]`` header if missing, updates the key
    line if present, otherwise appends it inside ``[daemon]``. Comments
    and unrelated lines are preserved.

    Args:
        key (str): a key in :data:`ALLOWED_KEYS`.
        value (str): the value to store.
        path (Path | None): config file. Defaults to ``config_path()``.
    """
    _check_key(key)
    use_path = path or config_path()
    lines = _config_lines(use_path)
    rendered = f"{key} = {_format_value(key, value)}"
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "[daemon]":
            header_idx = i
            break
    if header_idx is None:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append("[daemon]")
        lines.append(rendered)
    else:
        end = len(lines)
        for i in range(header_idx + 1, len(lines)):
            if lines[i].strip().startswith("["):
                end = i
                break
        for i in range(header_idx + 1, end):
            stripped = lines[i].strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            if stripped.split("=", 1)[0].strip() == key:
                lines[i] = rendered
                break
        else:
            lines.insert(end, rendered)
    use_path.parent.mkdir(parents=True, exist_ok=True)
    use_path.write_text("\n".join(lines) + "\n")


def unset_config(key: str, path: Path | None = None) -> None:
    """Remove ``key`` from the ``[daemon]`` table if present.

    Args:
        key (str): a key in :data:`ALLOWED_KEYS`.
        path (Path | None): config file. Defaults to ``config_path()``.
    """
    _check_key(key)
    use_path = path or config_path()
    if not use_path.exists():
        return
    lines = _config_lines(use_path)
    kept = []
    in_daemon = False
    for line in lines:
        stripped = line.strip()
        if stripped == "[daemon]":
            in_daemon = True
            kept.append(line)
            continue
        if stripped.startswith("["):
            in_daemon = False
        if (in_daemon and "=" in stripped and not stripped.startswith("#")
                and stripped.split("=", 1)[0].strip() == key):
            continue
        kept.append(line)
    use_path.write_text("\n".join(kept) + "\n")
