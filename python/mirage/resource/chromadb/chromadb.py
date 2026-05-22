from mirage.accessor.chromadb import ChromaDBAccessor
from mirage.core.chromadb.glob import resolve_glob as _resolve_glob
from mirage.resource.base import BaseResource
from mirage.resource.chromadb.config import ChromaDBConfig
from mirage.resource.chromadb.prompt import PROMPT
from mirage.types import ResourceName


class ChromaDBResource(BaseResource):

    name: str = ResourceName.CHROMADB
    is_remote: bool = True
    PROMPT: str = PROMPT

    def __init__(self, config: ChromaDBConfig) -> None:
        super().__init__()
        self.config = config
        self.accessor = ChromaDBAccessor(self.config)
        from mirage.commands.builtin.chromadb import COMMANDS
        from mirage.ops.chromadb import OPS as CHROMADB_VFS_OPS

        for fn in COMMANDS:
            self.register(fn)
        for fn in CHROMADB_VFS_OPS:
            self.register_op(fn)

    async def resolve_glob(self, paths, prefix: str = ""):
        return await _resolve_glob(self.accessor, paths, index=self._index)

    async def fingerprint(self, path: str) -> str | None:
        return None

    def get_state(self) -> dict:
        redacted = ["api_key"]
        cfg = self.config.model_dump()
        for field in redacted:
            if cfg.get(field) is not None:
                cfg[field] = "<REDACTED>"
        return {
            "type": self.name,
            "needs_override": True,
            "redacted_fields": redacted,
            "config": cfg,
        }

    def load_state(self, state: dict) -> None:
        pass
