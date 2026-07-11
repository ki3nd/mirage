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

import tomllib
from pathlib import Path


def read_daemon_table(home: Path) -> dict:
    """Read the ``[daemon]`` table from ``home/config.toml``.

    Args:
        home (Path): the ``.mirage`` base directory. The config file is
            ``home/config.toml``.

    Returns:
        dict: the ``[daemon]`` table, or ``{}`` if the file or table is
            absent.
    """
    path = home / "config.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    table = data.get("daemon", {})
    return table if isinstance(table, dict) else {}
