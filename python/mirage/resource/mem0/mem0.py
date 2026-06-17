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

from mirage.accessor.mem0 import Mem0Accessor
from mirage.core.mem0.glob import resolve_glob as _resolve_glob
from mirage.resource.base import BaseResource
from mirage.resource.mem0.config import Mem0Config
from mirage.resource.mem0.prompt import PROMPT
from mirage.types import ResourceName


class Mem0Resource(BaseResource):

    name: str = ResourceName.MEM0
    is_remote: bool = True
    PROMPT: str = PROMPT
    SUPPORTS_SNAPSHOT: bool = False

    def __init__(self, config: Mem0Config) -> None:
        super().__init__()
        self.config = config
        self.accessor = Mem0Accessor(self.config)
        from mirage.commands.builtin.mem0 import COMMANDS
        from mirage.ops.mem0 import OPS as MEM0_VFS_OPS

        for fn in COMMANDS:
            self.register(fn)
        for fn in MEM0_VFS_OPS:
            self.register_op(fn)

    async def resolve_glob(self, paths, prefix: str = ""):
        return await _resolve_glob(self.accessor, paths, index=self._index)

    async def fingerprint(self, path: str) -> str | None:
        return None

    def get_state(self) -> dict:
        return self.config_state(self.config)

    def load_state(self, state: dict) -> None:
        pass
