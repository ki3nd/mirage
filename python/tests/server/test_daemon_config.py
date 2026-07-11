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

from mirage.server.daemon_config import read_daemon_table


def test_read_daemon_table_missing_file(tmp_path):
    assert read_daemon_table(tmp_path) == {}


def test_read_daemon_table_no_daemon_section(tmp_path):
    (tmp_path / "config.toml").write_text("[other]\nx = 1\n")
    assert read_daemon_table(tmp_path) == {}


def test_read_daemon_table_reads_keys(tmp_path):
    (tmp_path / "config.toml"
     ).write_text('[daemon]\nurl = "http://h:1"\npid_file = "/tmp/p.pid"\n')
    table = read_daemon_table(tmp_path)
    assert table["url"] == "http://h:1"
    assert table["pid_file"] == "/tmp/p.pid"
