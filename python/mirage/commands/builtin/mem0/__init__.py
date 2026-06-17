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

from mirage.commands.builtin.mem0.cat import cat
from mirage.commands.builtin.mem0.find import find
from mirage.commands.builtin.mem0.grep import grep
from mirage.commands.builtin.mem0.head import head
from mirage.commands.builtin.mem0.jq import jq
from mirage.commands.builtin.mem0.ls import ls
from mirage.commands.builtin.mem0.rg import rg
from mirage.commands.builtin.mem0.search import search
from mirage.commands.builtin.mem0.stat import stat
from mirage.commands.builtin.mem0.tail import tail
from mirage.commands.builtin.mem0.tree import tree
from mirage.commands.builtin.mem0.wc import wc

COMMANDS = [cat, find, grep, head, jq, ls, rg, search, stat, tail, tree, wc]
