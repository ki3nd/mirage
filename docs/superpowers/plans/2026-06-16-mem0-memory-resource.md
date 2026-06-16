# mem0 "Memory" Resource Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `mem0` resource that mounts a single mem0 memory scope (one of user_id / agent_id / run_id) as a flat virtual filesystem of `<memory_id>.json` files, usable with `ls`, `cat`, `grep`, `find`, `head`, `tail`, `wc`, `tree`, `stat`, `jq`, plus a dedicated `search` command.

**Architecture:** Mirror the existing `langfuse` remote read-only resource: `config` → lazy `accessor` (wraps `mem0.AsyncMemoryClient`) → `core/mem0/*` (scope/readdir/read/stat/search/glob, index-cached) → thin `ops/mem0/*` `@op` wrappers → `commands/builtin/mem0/*` wiring-only wrappers that forward to the generic commands. `grep` is wired with a content-only reader so it matches the `memory` text, not metadata.

**Tech Stack:** Python 3.12, `uv`, pydantic v2, `mem0ai` (`mem0.AsyncMemoryClient`), pytest + `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-06-16-mem0-memory-resource-design.md`

**Conventions (apply to every new file):**
- Start each `mirage/...` source file with the standard Apache license header block used across the repo (copy from any sibling, e.g. `mirage/resource/langfuse/langfuse.py` lines 1-13). Test files have **no** header and **no** `__init__.py` (CLAUDE.md).
- All imports at top of file. No nested functions. No per-line comments. Paths are `PathSpec`.
- Run all `uv`/`pytest` commands from `python/`.

---

## Task 1: Wire dependency, ResourceName, registry

**Files:**
- Modify: `python/pyproject.toml` (the `all` meta-extra, ~line 147-174)
- Modify: `python/mirage/types.py` (`ResourceName`, after `DIFY = "dify"` ~line 179)
- Modify: `python/mirage/resource/registry.py` (`REGISTRY`, after the `dify` entry ~line 146-148)

- [ ] **Step 1: Confirm the `mem0` extra exists**

Run: `cd python && grep -n '^mem0' pyproject.toml`
Expected: a line like `mem0 = ["mem0ai>=2.0.6"]` (added earlier via `uv add --optional mem0 mem0ai`). If missing, run `uv add --optional mem0 mem0ai`.

- [ ] **Step 2: Add `mem0` to the `all` meta-extra**

In `python/pyproject.toml`, inside the `all = [ ... ]` list, add after the `langfuse` line:

```toml
    "mirage-ai[mem0]",
```

- [ ] **Step 3: Add the `ResourceName` enum member**

In `python/mirage/types.py`, directly after `DIFY = "dify"`:

```python
    MEM0 = "mem0"
```

- [ ] **Step 4: Add the registry entry**

In `python/mirage/resource/registry.py`, add to the `REGISTRY` dict (after the `"dify"` entry):

```python
    "mem0":
    ResourceEntry("mirage.resource.mem0:Mem0Resource",
                  "mirage.resource.mem0:Mem0Config"),
```

- [ ] **Step 5: Verify it imports (resource module does not exist yet, so only enum/registry parse)**

Run: `cd python && uv run python -c "from mirage.types import ResourceName; print(ResourceName.MEM0.value)"`
Expected: `mem0`

- [ ] **Step 6: Commit**

```bash
git add python/pyproject.toml python/mirage/types.py python/mirage/resource/registry.py
git commit -m "feat(mem0): register mem0 resource name, registry entry, extra"
```

---

## Task 2: `Mem0Config`

**Files:**
- Create: `python/mirage/resource/mem0/__init__.py`
- Create: `python/mirage/resource/mem0/config.py`
- Test: `python/tests/resource/mem0/test_config.py`

- [ ] **Step 1: Write the failing test**

`python/tests/resource/mem0/test_config.py`:

```python
import pytest
from pydantic import SecretStr, ValidationError

from mirage.resource.mem0.config import Mem0Config


def test_scope_filter_user():
    cfg = Mem0Config(api_key=SecretStr("k"), user_id="alex")
    assert cfg.scope_filter == {"user_id": "alex"}
    assert cfg.scope_kind == "user"


def test_scope_filter_agent():
    cfg = Mem0Config(api_key=SecretStr("k"), agent_id="routine_agent")
    assert cfg.scope_filter == {"agent_id": "routine_agent"}
    assert cfg.scope_kind == "agent"


def test_requires_exactly_one_entity_none_set():
    with pytest.raises(ValidationError):
        Mem0Config(api_key=SecretStr("k"))


def test_requires_exactly_one_entity_two_set():
    with pytest.raises(ValidationError):
        Mem0Config(api_key=SecretStr("k"), user_id="a", agent_id="b")


def test_defaults():
    cfg = Mem0Config(api_key=SecretStr("k"), run_id="r")
    assert cfg.host == "https://api.mem0.ai"
    assert cfg.default_page_size == 100
    assert cfg.default_search_limit == 10
    assert cfg.scope_filter == {"run_id": "r"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/resource/mem0/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mirage.resource.mem0'`

- [ ] **Step 3: Create the package init**

`python/mirage/resource/mem0/__init__.py` (with license header):

```python
from mirage.resource.mem0.config import Mem0Config

__all__ = ["Mem0Config", "Mem0Resource"]


def __getattr__(name: str):
    if name == "Mem0Resource":
        from mirage.resource.mem0.mem0 import Mem0Resource
        return Mem0Resource
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Write `config.py`**

`python/mirage/resource/mem0/config.py` (with license header):

```python
from pydantic import BaseModel, SecretStr, model_validator


class Mem0Config(BaseModel):
    api_key: SecretStr
    host: str = "https://api.mem0.ai"
    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    default_page_size: int = 100
    default_search_limit: int = 10

    @model_validator(mode="after")
    def _exactly_one_entity(self) -> "Mem0Config":
        present = [
            k for k in ("user_id", "agent_id", "run_id")
            if getattr(self, k) is not None
        ]
        if len(present) != 1:
            raise ValueError(
                "Mem0Config requires exactly one of user_id, agent_id, run_id; "
                f"got {present or 'none'}")
        return self

    @property
    def scope_kind(self) -> str:
        for kind in ("user", "agent", "run"):
            if getattr(self, f"{kind}_id") is not None:
                return kind
        raise ValueError("no scope set")

    @property
    def scope_filter(self) -> dict[str, str]:
        key = f"{self.scope_kind}_id"
        return {key: getattr(self, key)}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd python && uv run pytest tests/resource/mem0/test_config.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add python/mirage/resource/mem0/__init__.py python/mirage/resource/mem0/config.py python/tests/resource/mem0/test_config.py
git commit -m "feat(mem0): Mem0Config with single-entity scope validation"
```

---

## Task 3: `Mem0Accessor` (lazy client)

**Files:**
- Create: `python/mirage/accessor/mem0.py`
- Test: `python/tests/accessor/test_mem0.py`

- [ ] **Step 1: Write the failing test**

`python/tests/accessor/test_mem0.py`:

```python
from pydantic import SecretStr

from mirage.accessor.mem0 import Mem0Accessor
from mirage.resource.mem0.config import Mem0Config


def test_client_is_lazy(monkeypatch):
    built = {"n": 0}

    class FakeClient:
        def __init__(self, **kwargs):
            built["n"] += 1
            self.kwargs = kwargs

    monkeypatch.setattr("mirage.accessor.mem0.AsyncMemoryClient", FakeClient)
    cfg = Mem0Config(api_key=SecretStr("secret-key"), user_id="alex")
    accessor = Mem0Accessor(cfg)
    assert built["n"] == 0
    client = accessor.client
    assert built["n"] == 1
    assert client.kwargs["api_key"] == "secret-key"
    assert client.kwargs["host"] == "https://api.mem0.ai"
    assert accessor.client is client
    assert built["n"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/accessor/test_mem0.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mirage.accessor.mem0'`

- [ ] **Step 3: Write `accessor/mem0.py`**

`python/mirage/accessor/mem0.py` (with license header):

```python
from mem0 import AsyncMemoryClient

from mirage.accessor.base import Accessor
from mirage.resource.mem0.config import Mem0Config
from mirage.resource.secrets import reveal_secret


class Mem0Accessor(Accessor):

    def __init__(self, config: Mem0Config) -> None:
        self.config = config
        self._client: AsyncMemoryClient | None = None

    @property
    def client(self) -> AsyncMemoryClient:
        if self._client is None:
            self._client = AsyncMemoryClient(
                api_key=reveal_secret(self.config.api_key),
                host=self.config.host,
            )
        return self._client
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/accessor/test_mem0.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/accessor/mem0.py python/tests/accessor/test_mem0.py
git commit -m "feat(mem0): lazy Mem0Accessor wrapping AsyncMemoryClient"
```

---

## Task 4: `core/mem0/_client.py` — async fetch helpers

**Files:**
- Create: `python/mirage/core/mem0/__init__.py` (empty, with license header)
- Create: `python/mirage/core/mem0/_client.py`
- Test: `python/tests/core/mem0/test_client.py`

- [ ] **Step 1: Write the failing test**

`python/tests/core/mem0/test_client.py`:

```python
import pytest

from mirage.core.mem0._client import (get_all_memories, get_memory,
                                       search_memories)


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    async def get_all(self, options=None):
        self.calls.append(options.model_dump(exclude_unset=True))
        page = options.page or 1
        return self.pages[page - 1]

    async def get(self, memory_id):
        return {"id": memory_id, "memory": "hi"}

    async def search(self, query, options=None):
        self.calls.append({"query": query, **options.model_dump(exclude_unset=True)})
        return {"results": [{"id": "1", "memory": "m", "score": 0.9}]}


@pytest.mark.asyncio
async def test_get_all_paginates():
    pages = [
        {"count": 3, "next": "x", "results": [{"id": "a"}, {"id": "b"}]},
        {"count": 3, "next": None, "results": [{"id": "c"}]},
    ]
    client = FakeClient(pages)
    out = await get_all_memories(client, {"user_id": "alex"}, page_size=2)
    assert [m["id"] for m in out] == ["a", "b", "c"]
    assert client.calls[0]["filters"] == {"user_id": "alex"}
    assert client.calls[0]["page"] == 1
    assert client.calls[1]["page"] == 2


@pytest.mark.asyncio
async def test_get_memory():
    client = FakeClient([])
    assert await get_memory(client, "xyz") == {"id": "xyz", "memory": "hi"}


@pytest.mark.asyncio
async def test_search():
    client = FakeClient([])
    out = await search_memories(client, "morning", {"agent_id": "a"},
                                top_k=5, threshold=0.0)
    assert out[0]["score"] == 0.9
    assert client.calls[0]["query"] == "morning"
    assert client.calls[0]["filters"] == {"agent_id": "a"}
    assert client.calls[0]["top_k"] == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/core/mem0/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mirage.core.mem0'`

- [ ] **Step 3: Write `_client.py`**

`python/mirage/core/mem0/_client.py` (with license header):

```python
from mem0.client.types import GetAllMemoryOptions, SearchMemoryOptions


async def get_all_memories(
    client,
    filters: dict,
    page_size: int = 100,
) -> list[dict]:
    """Fetch all memories for a scope, following pagination.

    Args:
        client (AsyncMemoryClient): mem0 async client.
        filters (dict): mem0 entity filter, e.g. {"user_id": "alex"}.
        page_size (int): page size per request.
    """
    results: list[dict] = []
    page = 1
    while True:
        options = GetAllMemoryOptions(
            filters=filters,
            page=page,
            page_size=page_size,
        )
        resp = await client.get_all(options=options)
        batch = resp.get("results", [])
        results.extend(batch)
        if not resp.get("next") or not batch:
            break
        page += 1
    return results


async def get_memory(client, memory_id: str) -> dict:
    """Fetch one memory by id.

    Args:
        client (AsyncMemoryClient): mem0 async client.
        memory_id (str): memory id.
    """
    return await client.get(memory_id)


async def search_memories(
    client,
    query: str,
    filters: dict,
    top_k: int = 10,
    threshold: float = 0.0,
) -> list[dict]:
    """Semantic search within a scope.

    Args:
        client (AsyncMemoryClient): mem0 async client.
        query (str): search query.
        filters (dict): mem0 entity filter.
        top_k (int): number of results.
        threshold (float): minimum similarity score.
    """
    options = SearchMemoryOptions(
        filters=filters,
        top_k=top_k,
        threshold=threshold,
    )
    resp = await client.search(query, options=options)
    return resp.get("results", [])
```

Also create `python/mirage/core/mem0/__init__.py` (license header only, empty body).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/core/mem0/test_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/core/mem0/__init__.py python/mirage/core/mem0/_client.py python/tests/core/mem0/test_client.py
git commit -m "feat(mem0): async client helpers (get_all paginated, get, search)"
```

---

## Task 5: `core/mem0/scope.py` — path detection

**Files:**
- Create: `python/mirage/core/mem0/scope.py`
- Test: `python/tests/core/mem0/test_scope.py`

The flat tree has two levels: root (a directory) and `<id>.json` (a memory file).

- [ ] **Step 1: Write the failing test**

`python/tests/core/mem0/test_scope.py`:

```python
from mirage.core.mem0.scope import detect
from mirage.types import PathSpec


def test_root():
    s = detect(PathSpec(original="/mem", directory="/mem", prefix="/mem"))
    assert s.level == "root"
    assert s.memory_id is None


def test_memory_file():
    p = PathSpec(original="/mem/abc.json", directory="/mem", prefix="/mem")
    s = detect(p)
    assert s.level == "memory"
    assert s.memory_id == "abc"


def test_hidden_is_root_miss():
    p = PathSpec(original="/mem/.secret", directory="/mem", prefix="/mem")
    s = detect(p)
    assert s.level == "invalid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/core/mem0/test_scope.py -v`
Expected: FAIL — `ModuleNotFoundError: ...scope`

- [ ] **Step 3: Write `scope.py`**

`python/mirage/core/mem0/scope.py` (with license header):

```python
from dataclasses import dataclass

from mirage.types import PathSpec


@dataclass
class Mem0Scope:
    level: str
    memory_id: str | None = None


def _backend_key(path: PathSpec) -> str:
    raw = path.original
    prefix = path.prefix
    if prefix and raw.startswith(prefix):
        rest = raw[len(prefix):]
        if prefix.endswith("/") or rest == "" or rest.startswith("/"):
            raw = rest or "/"
    return raw.strip("/")


def detect(path: PathSpec) -> Mem0Scope:
    """Classify a mem0 virtual path.

    Args:
        path (PathSpec): the virtual path to classify.
    """
    key = _backend_key(path)
    if not key:
        return Mem0Scope(level="root")
    parts = key.split("/")
    if any(p.startswith(".") for p in parts):
        return Mem0Scope(level="invalid")
    if len(parts) == 1 and parts[0].endswith(".json"):
        return Mem0Scope(level="memory", memory_id=parts[0][:-len(".json")])
    return Mem0Scope(level="invalid")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/core/mem0/test_scope.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/core/mem0/scope.py python/tests/core/mem0/test_scope.py
git commit -m "feat(mem0): path scope detection (root vs memory file)"
```

---

## Task 6: `core/mem0/readdir.py` — cache-first listing

**Files:**
- Create: `python/mirage/core/mem0/readdir.py`
- Test: `python/tests/core/mem0/test_readdir.py`

- [ ] **Step 1: Write the failing test**

`python/tests/core/mem0/test_readdir.py`:

```python
import pytest

from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import RAMIndexCacheStore
from mirage.core.mem0.readdir import readdir
from mirage.resource.mem0.config import Mem0Config
from mirage.types import PathSpec
from pydantic import SecretStr


class FakeClient:
    def __init__(self):
        self.get_all_calls = 0

    async def get_all(self, options=None):
        self.get_all_calls += 1
        return {
            "count": 2,
            "next": None,
            "results": [
                {"id": "aaa", "memory": "first"},
                {"id": "bbb", "memory": "second"},
            ],
        }


def _accessor():
    cfg = Mem0Config(api_key=SecretStr("k"), user_id="alex")
    acc = Mem0Accessor(cfg)
    acc._client = FakeClient()
    return acc


@pytest.mark.asyncio
async def test_readdir_lists_memory_files():
    acc = _accessor()
    index = RAMIndexCacheStore()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    names = await readdir(acc, p, index)
    assert sorted(names) == ["/mem/aaa.json", "/mem/bbb.json"]


@pytest.mark.asyncio
async def test_readdir_uses_cache_second_call():
    acc = _accessor()
    index = RAMIndexCacheStore()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    await readdir(acc, p, index)
    await readdir(acc, p, index)
    assert acc._client.get_all_calls == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/core/mem0/test_readdir.py -v`
Expected: FAIL — `ModuleNotFoundError: ...readdir`

- [ ] **Step 3: Write `readdir.py`**

`python/mirage/core/mem0/readdir.py` (with license header):

```python
import json

from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import IndexCacheStore, IndexEntry
from mirage.core.mem0._client import get_all_memories
from mirage.core.mem0.scope import detect
from mirage.types import PathSpec
from mirage.utils.errors import enoent, enotdir


def _json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode()


async def readdir(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
) -> list[str]:
    """List the memory files for the configured scope.

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        path (PathSpec): the directory path (only the mount root is a dir).
        index (IndexCacheStore | None): index cache.
    """
    if isinstance(path, str):
        path = PathSpec(original=path, directory=path)
    scope = detect(path)
    if scope.level == "invalid":
        raise enoent(path.original)
    if scope.level != "root":
        raise enotdir(path.original)

    prefix = path.prefix
    virtual_key = prefix or "/"

    if index is not None:
        listing = await index.list_dir(virtual_key)
        if listing.entries is not None:
            return listing.entries

    memories = await get_all_memories(
        accessor.client,
        filters=accessor.config.scope_filter,
        page_size=accessor.config.default_page_size,
    )
    entries: list[tuple[str, IndexEntry]] = []
    names: list[str] = []
    for m in memories:
        filename = f"{m['id']}.json"
        body = _json_bytes(m)
        entry = IndexEntry(
            id=m["id"],
            name=m["id"],
            resource_type="mem0/memory",
            vfs_name=filename,
            size=len(body),
            extra={"memory": m},
        )
        entries.append((filename, entry))
        names.append(f"{prefix}/{filename}")
    if index is not None:
        await index.set_dir(virtual_key, entries)
    return names
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/core/mem0/test_readdir.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/core/mem0/readdir.py python/tests/core/mem0/test_readdir.py
git commit -m "feat(mem0): cache-first readdir over scope memories"
```

---

## Task 7: `core/mem0/read.py` — full JSON + content projection

**Files:**
- Create: `python/mirage/core/mem0/read.py`
- Test: `python/tests/core/mem0/test_read.py`

`read` returns the full memory JSON; `read_content` returns only the `memory` text (used by grep). Both reuse the primed index entry (`extra["memory"]`) when available, else call `get`.

- [ ] **Step 1: Write the failing test**

`python/tests/core/mem0/test_read.py`:

```python
import json

import pytest
from pydantic import SecretStr

from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import RAMIndexCacheStore
from mirage.core.mem0.read import read, read_content
from mirage.core.mem0.readdir import readdir
from mirage.resource.mem0.config import Mem0Config
from mirage.types import PathSpec


class FakeClient:
    def __init__(self):
        self.get_calls = 0

    async def get_all(self, options=None):
        return {"count": 1, "next": None,
                "results": [{"id": "aaa", "memory": "loves bananas",
                             "categories": ["food"]}]}

    async def get(self, memory_id):
        self.get_calls += 1
        return {"id": memory_id, "memory": "loves bananas",
                "categories": ["food"]}


def _accessor():
    cfg = Mem0Config(api_key=SecretStr("k"), user_id="alex")
    acc = Mem0Accessor(cfg)
    acc._client = FakeClient()
    return acc


@pytest.mark.asyncio
async def test_read_full_json_from_cache_no_get():
    acc = _accessor()
    index = RAMIndexCacheStore()
    root = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    await readdir(acc, root, index)
    fpath = PathSpec(original="/mem/aaa.json", directory="/mem", prefix="/mem")
    data = json.loads(await read(acc, fpath, index))
    assert data["categories"] == ["food"]
    assert acc._client.get_calls == 0


@pytest.mark.asyncio
async def test_read_content_only_memory_text():
    acc = _accessor()
    index = RAMIndexCacheStore()
    root = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    await readdir(acc, root, index)
    fpath = PathSpec(original="/mem/aaa.json", directory="/mem", prefix="/mem")
    assert await read_content(acc, fpath, index) == b"loves bananas\n"


@pytest.mark.asyncio
async def test_read_falls_back_to_get_when_no_cache():
    acc = _accessor()
    index = RAMIndexCacheStore()
    fpath = PathSpec(original="/mem/zzz.json", directory="/mem", prefix="/mem")
    data = json.loads(await read(acc, fpath, index))
    assert data["id"] == "zzz"
    assert acc._client.get_calls == 1


@pytest.mark.asyncio
async def test_read_missing_path_enoent():
    acc = _accessor()
    with pytest.raises(FileNotFoundError):
        await read(acc, PathSpec(original="/mem", directory="/mem",
                                 prefix="/mem"), RAMIndexCacheStore())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/core/mem0/test_read.py -v`
Expected: FAIL — `ModuleNotFoundError: ...read`

- [ ] **Step 3: Write `read.py`**

`python/mirage/core/mem0/read.py` (with license header):

```python
import json

from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import IndexCacheStore
from mirage.core.mem0._client import get_memory
from mirage.core.mem0.scope import detect
from mirage.types import PathSpec
from mirage.utils.errors import enoent


def _json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode()


async def _resolve_memory(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore | None,
) -> dict:
    if isinstance(path, str):
        path = PathSpec(original=path, directory=path)
    scope = detect(path)
    if scope.level != "memory":
        raise enoent(path.original)
    if index is not None:
        lookup = await index.get(path.original)
        if lookup.entry is not None and lookup.entry.extra.get("memory"):
            return lookup.entry.extra["memory"]
    return await get_memory(accessor.client, scope.memory_id)


async def read(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
) -> bytes:
    """Read a memory as full JSON bytes.

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        path (PathSpec): the memory file path.
        index (IndexCacheStore | None): index cache.
    """
    memory = await _resolve_memory(accessor, path, index)
    return _json_bytes(memory)


async def read_content(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
) -> bytes:
    """Read only the memory text (used by grep).

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        path (PathSpec): the memory file path.
        index (IndexCacheStore | None): index cache.
    """
    memory = await _resolve_memory(accessor, path, index)
    text = memory.get("memory", "")
    return (text + "\n").encode()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/core/mem0/test_read.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/core/mem0/read.py python/tests/core/mem0/test_read.py
git commit -m "feat(mem0): read full JSON and content-only projection"
```

---

## Task 8: `core/mem0/stat.py`

**Files:**
- Create: `python/mirage/core/mem0/stat.py`
- Test: `python/tests/core/mem0/test_stat.py`

- [ ] **Step 1: Write the failing test**

`python/tests/core/mem0/test_stat.py`:

```python
import pytest
from pydantic import SecretStr

from mirage.accessor.mem0 import Mem0Accessor
from mirage.core.mem0.stat import stat
from mirage.resource.mem0.config import Mem0Config
from mirage.types import FileType, PathSpec


def _accessor():
    cfg = Mem0Config(api_key=SecretStr("k"), user_id="alex")
    return Mem0Accessor(cfg)


@pytest.mark.asyncio
async def test_stat_root_is_dir():
    s = await stat(_accessor(),
                   PathSpec(original="/mem", directory="/mem", prefix="/mem"))
    assert s.type == FileType.DIRECTORY


@pytest.mark.asyncio
async def test_stat_memory_is_json():
    s = await stat(_accessor(),
                   PathSpec(original="/mem/aaa.json", directory="/mem",
                            prefix="/mem"))
    assert s.type == FileType.JSON
    assert s.name == "aaa.json"


@pytest.mark.asyncio
async def test_stat_invalid_enoent():
    with pytest.raises(FileNotFoundError):
        await stat(_accessor(),
                   PathSpec(original="/mem/.x", directory="/mem", prefix="/mem"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/core/mem0/test_stat.py -v`
Expected: FAIL — `ModuleNotFoundError: ...stat`

- [ ] **Step 3: Write `stat.py`**

`python/mirage/core/mem0/stat.py` (with license header):

```python
from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import IndexCacheStore
from mirage.core.mem0.scope import detect
from mirage.types import FileStat, FileType, PathSpec
from mirage.utils.errors import enoent


async def stat(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
) -> FileStat:
    """Stat a mem0 path.

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        path (PathSpec): the path to stat.
        index (IndexCacheStore | None): index cache.
    """
    if isinstance(path, str):
        path = PathSpec(original=path, directory=path)
    scope = detect(path)
    if scope.level == "root":
        return FileStat(name="/", type=FileType.DIRECTORY)
    if scope.level == "memory":
        return FileStat(name=f"{scope.memory_id}.json", type=FileType.JSON)
    raise enoent(path.original)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/core/mem0/test_stat.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/core/mem0/stat.py python/tests/core/mem0/test_stat.py
git commit -m "feat(mem0): stat (root dir, memory json)"
```

---

## Task 9: `core/mem0/glob.py`

**Files:**
- Create: `python/mirage/core/mem0/glob.py`
- Test: `python/tests/core/mem0/test_glob.py`

Mirror `core/langfuse/glob.py` (resolve `*` patterns via `readdir`).

- [ ] **Step 1: Write the failing test**

`python/tests/core/mem0/test_glob.py`:

```python
import pytest
from pydantic import SecretStr

from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import RAMIndexCacheStore
from mirage.core.mem0.glob import resolve_glob
from mirage.resource.mem0.config import Mem0Config
from mirage.types import PathSpec


class FakeClient:
    async def get_all(self, options=None):
        return {"count": 2, "next": None,
                "results": [{"id": "aaa", "memory": "x"},
                            {"id": "bbb", "memory": "y"}]}


def _accessor():
    cfg = Mem0Config(api_key=SecretStr("k"), user_id="alex")
    acc = Mem0Accessor(cfg)
    acc._client = FakeClient()
    return acc


@pytest.mark.asyncio
async def test_passthrough_non_pattern():
    acc = _accessor()
    p = PathSpec(original="/mem/aaa.json", directory="/mem", prefix="/mem",
                 resolved=True)
    out = await resolve_glob(acc, [p], RAMIndexCacheStore())
    assert out == [p]


@pytest.mark.asyncio
async def test_expands_star():
    acc = _accessor()
    p = PathSpec(original="/mem/*.json", directory="/mem", prefix="/mem",
                 pattern="*.json")
    out = await resolve_glob(acc, [p], RAMIndexCacheStore())
    assert sorted(x.original for x in out) == ["/mem/aaa.json", "/mem/bbb.json"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/core/mem0/test_glob.py -v`
Expected: FAIL — `ModuleNotFoundError: ...glob`

- [ ] **Step 3: Write `glob.py`**

`python/mirage/core/mem0/glob.py` (with license header) — same structure as `core/langfuse/glob.py`:

```python
import fnmatch
import logging

from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.constants import SCOPE_ERROR
from mirage.core.mem0.readdir import readdir
from mirage.types import PathSpec

logger = logging.getLogger(__name__)


async def resolve_glob(
    accessor: Mem0Accessor,
    paths: list[PathSpec],
    index: IndexCacheStore = None,
) -> list[PathSpec]:
    result: list[PathSpec] = []
    for p in paths:
        if isinstance(p, str):
            result.append(PathSpec(original=p, directory=p))
            continue
        if p.resolved:
            result.append(p)
        elif p.pattern:
            entries = await readdir(accessor, p.dir, index)
            matched = [
                PathSpec(
                    original=e,
                    directory=p.directory,
                    prefix=p.prefix,
                ) for e in entries
                if fnmatch.fnmatch(e.rsplit("/", 1)[-1], p.pattern)
            ]
            if len(matched) > SCOPE_ERROR:
                logger.warning(
                    "%s: %d matches exceeds limit (%d), truncating",
                    p.directory,
                    len(matched),
                    SCOPE_ERROR,
                )
                matched = matched[:SCOPE_ERROR]
            result.extend(matched)
        else:
            result.append(p)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/core/mem0/test_glob.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/core/mem0/glob.py python/tests/core/mem0/test_glob.py
git commit -m "feat(mem0): glob resolution over flat listing"
```

---

## Task 10: `core/mem0/search.py` — semantic search rendering

**Files:**
- Create: `python/mirage/core/mem0/search.py`
- Test: `python/tests/core/mem0/test_search.py`

Renders results as `<id>.json:<score>` header then the memory text (dify-style), scoped to the configured filter.

- [ ] **Step 1: Write the failing test**

`python/tests/core/mem0/test_search.py`:

```python
import pytest
from pydantic import SecretStr

from mirage.accessor.mem0 import Mem0Accessor
from mirage.core.mem0.search import search_memories_rendered
from mirage.resource.mem0.config import Mem0Config


class FakeClient:
    def __init__(self):
        self.calls = []

    async def search(self, query, options=None):
        self.calls.append((query, options.model_dump(exclude_unset=True)))
        return {"results": [
            {"id": "aaa", "memory": "eats banana", "score": 0.91},
            {"id": "bbb", "memory": "likes sci-fi", "score": 0.70},
        ]}


def _accessor():
    cfg = Mem0Config(api_key=SecretStr("k"), agent_id="routine_agent")
    acc = Mem0Accessor(cfg)
    acc._client = FakeClient()
    return acc


@pytest.mark.asyncio
async def test_search_renders_ranked():
    acc = _accessor()
    out = await search_memories_rendered(acc, "morning", prefix="/mem",
                                         top_k=5, threshold=0.0)
    text = out.decode()
    assert "/mem/aaa.json:0.91" in text
    assert "eats banana" in text
    assert acc._client.calls[0][1]["filters"] == {"agent_id": "routine_agent"}
    assert acc._client.calls[0][1]["top_k"] == 5


@pytest.mark.asyncio
async def test_search_empty():
    acc = _accessor()
    acc._client.search = _empty_search
    out = await search_memories_rendered(acc, "nope", prefix="/mem", top_k=5,
                                         threshold=0.0)
    assert out == b""


async def _empty_search(query, options=None):
    return {"results": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/core/mem0/test_search.py -v`
Expected: FAIL — `ModuleNotFoundError: ...search`

- [ ] **Step 3: Write `search.py`**

`python/mirage/core/mem0/search.py` (with license header):

```python
from mirage.accessor.mem0 import Mem0Accessor
from mirage.core.mem0._client import search_memories
from mirage.utils.score import format_score


def _validate(query: str, top_k: int, threshold: float) -> None:
    if not query:
        raise ValueError("search: query is required")
    if top_k <= 0:
        raise ValueError("search: top-k must be positive")
    if threshold < 0 or threshold > 1:
        raise ValueError("search: threshold must be in [0, 1]")


async def search_memories_rendered(
    accessor: Mem0Accessor,
    query: str,
    *,
    prefix: str,
    top_k: int,
    threshold: float,
) -> bytes:
    """Run a semantic search in the scope and render ranked results.

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        query (str): search query.
        prefix (str): mount prefix for rendered paths.
        top_k (int): number of results.
        threshold (float): minimum similarity score.
    """
    _validate(query, top_k, threshold)
    results = await search_memories(
        accessor.client,
        query,
        accessor.config.scope_filter,
        top_k=top_k,
        threshold=threshold,
    )
    lines: list[str] = []
    for r in results:
        path = f"{prefix}/{r['id']}.json"
        score = format_score(r.get("score"))
        header = path if score is None else f"{path}:{score}"
        lines.append(f"{header}\n{r.get('memory', '')}")
    if not lines:
        return b""
    return ("\n".join(lines) + "\n").encode()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/core/mem0/test_search.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/core/mem0/search.py python/tests/core/mem0/test_search.py
git commit -m "feat(mem0): semantic search rendering scoped to config filter"
```

---

## Task 11: `ops/mem0/*` — @op wrappers

**Files:**
- Create: `python/mirage/ops/mem0/__init__.py`
- Create: `python/mirage/ops/mem0/readdir.py`
- Create: `python/mirage/ops/mem0/read.py`
- Create: `python/mirage/ops/mem0/stat.py`
- Test: `python/tests/ops/mem0/test_ops.py`

- [ ] **Step 1: Write the failing test**

`python/tests/ops/mem0/test_ops.py`:

```python
from mirage.ops.mem0 import OPS


def test_ops_registered():
    names = set()
    for fn in OPS:
        for ro in fn._registered_ops:
            names.add((ro.name, ro.resource))
    assert ("readdir", "mem0") in names
    assert ("read", "mem0") in names
    assert ("stat", "mem0") in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/ops/mem0/test_ops.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mirage.ops.mem0'`

- [ ] **Step 3: Write the three op wrappers**

`python/mirage/ops/mem0/readdir.py` (with license header):

```python
from mirage.accessor.mem0 import Mem0Accessor
from mirage.core.mem0.readdir import readdir as core_readdir
from mirage.ops.registry import op
from mirage.types import PathSpec


@op("readdir", resource="mem0")
async def readdir(accessor: Mem0Accessor, path: PathSpec, *, index,
                  **kwargs) -> list[str]:
    return await core_readdir(accessor, path, index)
```

`python/mirage/ops/mem0/read.py` (with license header):

```python
from mirage.accessor.mem0 import Mem0Accessor
from mirage.core.mem0.read import read as core_read
from mirage.ops.registry import op
from mirage.types import PathSpec


@op("read", resource="mem0")
async def read(accessor: Mem0Accessor, path: PathSpec, *, index,
               **kwargs) -> bytes:
    return await core_read(accessor, path, index)
```

`python/mirage/ops/mem0/stat.py` (with license header):

```python
from mirage.accessor.mem0 import Mem0Accessor
from mirage.core.mem0.stat import stat as core_stat
from mirage.ops.registry import op
from mirage.types import FileStat, PathSpec


@op("stat", resource="mem0")
async def stat(accessor: Mem0Accessor, path: PathSpec, *, index,
               **kwargs) -> FileStat:
    return await core_stat(accessor, path, index)
```

`python/mirage/ops/mem0/__init__.py` (with license header):

```python
from mirage.ops.mem0.read import read
from mirage.ops.mem0.readdir import readdir
from mirage.ops.mem0.stat import stat

OPS = [read, readdir, stat]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && uv run pytest tests/ops/mem0/test_ops.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add python/mirage/ops/mem0 python/tests/ops/mem0/test_ops.py
git commit -m "feat(mem0): op wrappers (readdir, read, stat)"
```

---

## Task 12: `prompt.py` + `Mem0Resource` + COMMANDS wiring

**Files:**
- Create: `python/mirage/resource/mem0/prompt.py`
- Create: `python/mirage/resource/mem0/mem0.py`
- Create: `python/mirage/commands/builtin/mem0/__init__.py` (temporary minimal COMMANDS)
- Test: `python/tests/resource/mem0/test_mem0.py`

The command wrappers come in Tasks 13-14; here the COMMANDS list starts empty and is filled as wrappers land. Write `__init__.py` with `COMMANDS = []` first, then append in later tasks.

- [ ] **Step 1: Write the failing test**

`python/tests/resource/mem0/test_mem0.py`:

```python
import pytest
from pydantic import SecretStr

from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import ResourceName


def test_resource_basic():
    cfg = Mem0Config(api_key=SecretStr("secret"), user_id="alex")
    res = Mem0Resource(cfg)
    assert res.name == ResourceName.MEM0
    assert res.is_remote is True
    assert res.SUPPORTS_SNAPSHOT is False


def test_get_state_redacts_api_key():
    cfg = Mem0Config(api_key=SecretStr("secret"), user_id="alex")
    res = Mem0Resource(cfg)
    state = res.get_state()
    assert state["type"] == ResourceName.MEM0
    assert "secret" not in str(state)


@pytest.mark.asyncio
async def test_fingerprint_none():
    cfg = Mem0Config(api_key=SecretStr("secret"), user_id="alex")
    res = Mem0Resource(cfg)
    assert await res.fingerprint("/mem/aaa.json") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && uv run pytest tests/resource/mem0/test_mem0.py -v`
Expected: FAIL — `ModuleNotFoundError: ...mem0.mem0`

- [ ] **Step 3: Write `prompt.py`**

`python/mirage/resource/mem0/prompt.py` (with license header):

```python
PROMPT = """\
{prefix}
  <memory-id>.json"""
```

- [ ] **Step 4: Write the temporary commands `__init__.py`**

`python/mirage/commands/builtin/mem0/__init__.py` (with license header):

```python
COMMANDS = []
```

- [ ] **Step 5: Write `mem0.py`**

`python/mirage/resource/mem0/mem0.py` (with license header):

```python
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd python && uv run pytest tests/resource/mem0/test_mem0.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Verify resource builds via registry**

Run: `cd python && uv run python -c "from mirage.resource.registry import build_resource; r = build_resource('mem0', {'api_key': 'k', 'user_id': 'alex'}); print(r.name)"`
Expected: `mem0`

- [ ] **Step 8: Commit**

```bash
git add python/mirage/resource/mem0/prompt.py python/mirage/resource/mem0/mem0.py python/mirage/commands/builtin/mem0/__init__.py python/tests/resource/mem0/test_mem0.py
git commit -m "feat(mem0): Mem0Resource, prompt, command package skeleton"
```

---

## Task 13: Mirror command wrappers (ls, cat, stat, head, tail, wc, find, tree, jq)

These are wiring-only wrappers identical to their `mirage/commands/builtin/langfuse/<cmd>.py` counterparts, with this **exact substitution applied to every import/identifier**:

| langfuse token | mem0 token |
|---|---|
| `mirage.accessor.langfuse` | `mirage.accessor.mem0` |
| `LangfuseAccessor` | `Mem0Accessor` |
| `mirage.commands.builtin.langfuse._provision` | `mirage.commands.builtin.mem0._provision` |
| `mirage.core.langfuse.glob` | `mirage.core.mem0.glob` |
| `mirage.core.langfuse.read` | `mirage.core.mem0.read` |
| `mirage.core.langfuse.readdir` | `mirage.core.mem0.readdir` |
| `mirage.core.langfuse.stat` | `mirage.core.mem0.stat` |
| `resource="langfuse"` | `resource="mem0"` |
| `langfuse_read` | `mem0_read` (alias of `mirage.core.mem0.read.read`) |

**Files:**
- Create: `python/mirage/commands/builtin/mem0/_provision.py`
- Create: `python/mirage/commands/builtin/mem0/{ls,cat,stat,head,tail,wc,find,tree,jq}.py`
- Modify: `python/mirage/commands/builtin/mem0/__init__.py`
- Test: `python/tests/commands/builtin/mem0/test_ls.py`, `test_cat.py`

- [ ] **Step 1: Create `_provision.py`**

Copy `mirage/commands/builtin/langfuse/_provision.py` verbatim, applying the substitution table (only the `LangfuseAccessor` import/type changes). Result `python/mirage/commands/builtin/mem0/_provision.py`:

```python
from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import IndexCacheStore
from mirage.provision.types import Precision, ProvisionResult
from mirage.types import PathSpec


async def file_read_provision(
    accessor: Mem0Accessor,
    paths: list[PathSpec],
    command: str,
    index: IndexCacheStore = None,
) -> ProvisionResult:
    if not paths:
        return ProvisionResult(command=command, precision=Precision.UNKNOWN)
    ops = 0
    if index is not None:
        for p in paths:
            path_str = p.original if isinstance(p, PathSpec) else p
            lookup = await index.get(path_str)
            if lookup.entry is not None:
                ops += 1
    return ProvisionResult(
        command=command,
        network_read_low=0,
        network_read_high=0,
        read_ops=ops,
        precision=Precision.EXACT,
    )


async def metadata_provision(command: str) -> ProvisionResult:
    return ProvisionResult(
        command=command,
        network_read_low=0,
        network_read_high=0,
        read_ops=0,
        precision=Precision.EXACT,
    )
```

- [ ] **Step 2: Create the wrappers `ls.py`, `cat.py`, `stat.py`, `head.py`, `tail.py`, `wc.py`, `find.py`, `tree.py`, `jq.py`**

For each, copy the matching `mirage/commands/builtin/langfuse/<cmd>.py` and apply the substitution table. Where langfuse imports `read as langfuse_read`, change to `from mirage.core.mem0.read import read as mem0_read` and rename uses to `mem0_read`. Do **not** change command flag signatures.

Example — `python/mirage/commands/builtin/mem0/cat.py`:

```python
from collections.abc import AsyncIterator

from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.generic.cat import cat as generic_cat
from mirage.commands.builtin.mem0._provision import file_read_provision
from mirage.commands.builtin.utils.stream import _resolve_source
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.mem0.glob import resolve_glob
from mirage.core.mem0.read import read as mem0_read
from mirage.io.types import ByteSource, IOResult
from mirage.provision.types import ProvisionResult
from mirage.types import PathSpec


async def cat_provision(
    accessor: Mem0Accessor,
    paths: list[PathSpec],
    *texts: str,
    **_extra: object,
) -> ProvisionResult:
    return await file_read_provision(
        accessor, paths,
        "cat " + " ".join(p.original if isinstance(p, PathSpec) else p
                          for p in paths))


@command("cat", resource="mem0", spec=SPECS["cat"], provision=cat_provision)
async def cat(
    accessor: Mem0Accessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: AsyncIterator[bytes] | bytes | None = None,
    n: bool = False,
    index: IndexCacheStore = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    if paths:
        paths = await resolve_glob(accessor, paths, index)
        reads = {
            p.strip_prefix: await mem0_read(accessor, p, index)
            for p in paths
        }
        merged = b"".join(reads.values())
        io = IOResult(reads=reads, cache=list(reads))
        if n:
            return generic_cat(merged, number_lines=True), io
        return merged, io
    source = _resolve_source(stdin, "cat: missing operand")
    if n:
        return generic_cat(source, number_lines=True), IOResult()
    return source, IOResult()
```

For `ls.py`, `stat.py`, `head.py`, `tail.py`, `wc.py`, `find.py`, `tree.py`, `jq.py`: reproduce the corresponding langfuse file with the substitution table applied. Note `ls.py` and `find.py` also import `from mirage.core.mem0.readdir import readdir`/`stat`; keep the `LsSortBy`, `format_records`, `_parse_depth`, etc. imports unchanged (they are generic).

- [ ] **Step 3: Update `__init__.py`**

`python/mirage/commands/builtin/mem0/__init__.py`:

```python
from mirage.commands.builtin.mem0.cat import cat
from mirage.commands.builtin.mem0.find import find
from mirage.commands.builtin.mem0.head import head
from mirage.commands.builtin.mem0.jq import jq
from mirage.commands.builtin.mem0.ls import ls
from mirage.commands.builtin.mem0.stat import stat
from mirage.commands.builtin.mem0.tail import tail
from mirage.commands.builtin.mem0.tree import tree
from mirage.commands.builtin.mem0.wc import wc

COMMANDS = [cat, find, head, jq, ls, stat, tail, tree, wc]
```

- [ ] **Step 4: Write tests for ls and cat**

`python/tests/commands/builtin/mem0/test_ls.py`:

```python
import pytest
from pydantic import SecretStr

from mirage.cache.index import RAMIndexCacheStore
from mirage.commands.builtin.mem0.ls import ls
from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import PathSpec


class FakeClient:
    async def get_all(self, options=None):
        return {"count": 2, "next": None,
                "results": [{"id": "aaa", "memory": "x"},
                            {"id": "bbb", "memory": "y"}]}


def _res():
    res = Mem0Resource(Mem0Config(api_key=SecretStr("k"), user_id="alex"))
    res.accessor._client = FakeClient()
    return res


@pytest.mark.asyncio
async def test_ls_lists_memories():
    res = _res()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    source, _io = await ls.__wrapped__(res.accessor, [p], index=res._index,
                                       cwd=p)
    out = b"".join([chunk async for chunk in source]) if hasattr(
        source, "__aiter__") else source
    text = out.decode()
    assert "aaa.json" in text and "bbb.json" in text
```

`python/tests/commands/builtin/mem0/test_cat.py`:

```python
import json

import pytest
from pydantic import SecretStr

from mirage.commands.builtin.mem0.cat import cat
from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import PathSpec


class FakeClient:
    async def get_all(self, options=None):
        return {"count": 1, "next": None,
                "results": [{"id": "aaa", "memory": "loves bananas"}]}

    async def get(self, memory_id):
        return {"id": memory_id, "memory": "loves bananas"}


def _res():
    res = Mem0Resource(Mem0Config(api_key=SecretStr("k"), user_id="alex"))
    res.accessor._client = FakeClient()
    return res


@pytest.mark.asyncio
async def test_cat_returns_full_json():
    res = _res()
    p = PathSpec(original="/mem/aaa.json", directory="/mem", prefix="/mem",
                 resolved=True)
    out, _io = await cat.__wrapped__(res.accessor, [p], index=res._index)
    data = json.loads(out)
    assert data["memory"] == "loves bananas"
```

- [ ] **Step 5: Run tests**

Run: `cd python && uv run pytest tests/commands/builtin/mem0/ -v`
Expected: PASS

- [ ] **Step 6: Verify package imports cleanly**

Run: `cd python && uv run python -c "import mirage.commands.builtin.mem0 as m; print([c.__name__ for c in m.COMMANDS])"`
Expected: prints the 9 command names.

- [ ] **Step 7: Commit**

```bash
git add python/mirage/commands/builtin/mem0 python/tests/commands/builtin/mem0
git commit -m "feat(mem0): mirror read commands (ls, cat, stat, head, tail, wc, find, tree, jq)"
```

---

## Task 14: `grep` (content-only) and `search` commands

**Files:**
- Create: `python/mirage/commands/builtin/mem0/grep.py`
- Create: `python/mirage/commands/builtin/mem0/search.py`
- Modify: `python/mirage/core/mem0/read.py` (add `read_content_stream`)
- Modify: `python/mirage/commands/builtin/mem0/__init__.py` (add grep, search)
- Test: `python/tests/commands/builtin/mem0/test_grep.py`, `test_search.py`

- [ ] **Step 1: Write the failing tests**

`python/tests/commands/builtin/mem0/test_grep.py`:

```python
import pytest
from pydantic import SecretStr

from mirage.commands.builtin.mem0.grep import grep
from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import PathSpec


class FakeClient:
    async def get_all(self, options=None):
        return {"count": 2, "next": None, "results": [
            {"id": "aaa", "memory": "loves bananas", "categories": ["food"]},
            {"id": "bbb", "memory": "likes sci-fi", "categories": ["movies"]},
        ]}


def _res():
    res = Mem0Resource(Mem0Config(api_key=SecretStr("k"), user_id="alex"))
    res.accessor._client = FakeClient()
    return res


@pytest.mark.asyncio
async def test_grep_matches_content():
    res = _res()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    source, _io = await grep.__wrapped__(res.accessor, [p], "bananas",
                                         index=res._index)
    out = b"".join([c async for c in source]) if hasattr(
        source, "__aiter__") else source
    assert b"bananas" in out


@pytest.mark.asyncio
async def test_grep_ignores_metadata():
    res = _res()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    source, _io = await grep.__wrapped__(res.accessor, [p], "food",
                                         index=res._index)
    out = b"".join([c async for c in source]) if hasattr(
        source, "__aiter__") else source
    assert out in (b"", None) or b"food" not in out
```

`python/tests/commands/builtin/mem0/test_search.py`:

```python
import pytest
from pydantic import SecretStr

from mirage.commands.builtin.mem0.search import search
from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import PathSpec


class FakeClient:
    async def search(self, query, options=None):
        return {"results": [{"id": "aaa", "memory": "eats banana",
                             "score": 0.9}]}


def _res():
    res = Mem0Resource(Mem0Config(api_key=SecretStr("k"), agent_id="ra"))
    res.accessor._client = FakeClient()
    return res


@pytest.mark.asyncio
async def test_search_command():
    res = _res()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    out, _io = await search.__wrapped__(res.accessor, [p], "morning",
                                        index=res._index)
    assert b"aaa.json" in out
    assert b"eats banana" in out


@pytest.mark.asyncio
async def test_search_requires_query():
    res = _res()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    with pytest.raises(ValueError):
        await search.__wrapped__(res.accessor, [p], index=res._index)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && uv run pytest tests/commands/builtin/mem0/test_grep.py tests/commands/builtin/mem0/test_search.py -v`
Expected: FAIL — `ModuleNotFoundError: ...grep` / `...search`

- [ ] **Step 3: Add `read_content_stream` to `core/mem0/read.py`**

Append to `python/mirage/core/mem0/read.py`:

```python
async def read_content_stream(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
):
    yield await read_content(accessor, path, index)
```

- [ ] **Step 4: Write `grep.py`**

`python/mirage/commands/builtin/mem0/grep.py` (with license header) — mirrors `langfuse/grep.py` but wires the **content** readers:

```python
from functools import partial

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.generic.grep import grep as generic_grep
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.mem0.glob import resolve_glob
from mirage.core.mem0.read import read_content, read_content_stream
from mirage.core.mem0.readdir import readdir
from mirage.core.mem0.stat import stat
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("grep", resource="mem0", spec=SPECS["grep"])
async def grep(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    index: IndexCacheStore = None,
    **flags: object,
) -> tuple[ByteSource | None, IOResult]:
    paths = await resolve_glob(accessor, paths, index)
    return await generic_grep(
        paths,
        texts,
        flags,
        readdir=readdir,
        stat=stat,
        read_bytes=read_content,
        read_stream=partial(read_content_stream, index=index),
        accessor=accessor,
        index=index,
    )
```

- [ ] **Step 5: Write `search.py`**

`python/mirage/commands/builtin/mem0/search.py` (with license header):

```python
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.mem0.search import search_memories_rendered
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("search", resource="mem0", spec=SPECS["search"])
async def search(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    top_k: str | int | None = None,
    threshold: str | float = 0.0,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    if not texts:
        raise ValueError("search: query is required")
    query = texts[0]
    limit = (int(top_k) if top_k is not None
             else accessor.config.default_search_limit)
    prefix = ""
    if paths:
        p0 = paths[0]
        prefix = p0.prefix if isinstance(p0, PathSpec) else ""
    output = await search_memories_rendered(
        accessor,
        query,
        prefix=prefix,
        top_k=limit,
        threshold=float(threshold),
    )
    return output, IOResult()
```

- [ ] **Step 6: Update `__init__.py`**

`python/mirage/commands/builtin/mem0/__init__.py` — add grep and search:

```python
from mirage.commands.builtin.mem0.cat import cat
from mirage.commands.builtin.mem0.find import find
from mirage.commands.builtin.mem0.grep import grep
from mirage.commands.builtin.mem0.head import head
from mirage.commands.builtin.mem0.jq import jq
from mirage.commands.builtin.mem0.ls import ls
from mirage.commands.builtin.mem0.search import search
from mirage.commands.builtin.mem0.stat import stat
from mirage.commands.builtin.mem0.tail import tail
from mirage.commands.builtin.mem0.tree import tree
from mirage.commands.builtin.mem0.wc import wc

COMMANDS = [cat, find, grep, head, jq, ls, search, stat, tail, tree, wc]
```

- [ ] **Step 7: Run tests**

Run: `cd python && uv run pytest tests/commands/builtin/mem0/test_grep.py tests/commands/builtin/mem0/test_search.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add python/mirage/commands/builtin/mem0/grep.py python/mirage/commands/builtin/mem0/search.py python/mirage/core/mem0/read.py python/mirage/commands/builtin/mem0/__init__.py python/tests/commands/builtin/mem0/test_grep.py python/tests/commands/builtin/mem0/test_search.py
git commit -m "feat(mem0): content-only grep and semantic search commands"
```

---

## Task 15: Full-suite verification, import sanity, lint

**Files:** none (verification only)

- [ ] **Step 1: Import every new module (no ImportError / circular import)**

Run:
```bash
cd python && uv run python -c "import mirage.resource.mem0, mirage.resource.mem0.mem0, mirage.accessor.mem0, mirage.core.mem0._client, mirage.core.mem0.scope, mirage.core.mem0.readdir, mirage.core.mem0.read, mirage.core.mem0.stat, mirage.core.mem0.glob, mirage.core.mem0.search, mirage.ops.mem0, mirage.commands.builtin.mem0; print('ok')"
```
Expected: `ok`

- [ ] **Step 2: Build via registry and inspect commands/ops**

Run:
```bash
cd python && uv run python -c "from mirage.resource.registry import build_resource; r = build_resource('mem0', {'api_key':'k','agent_id':'a'}); print(len(r.commands()), len(r.ops_list()))"
```
Expected: non-zero counts for both (11 commands, 3 ops).

- [ ] **Step 3: Run the whole mem0 test subtree**

Run: `cd python && uv run pytest tests/core/mem0 tests/resource/mem0 tests/accessor/test_mem0.py tests/ops/mem0 tests/commands/builtin/mem0 -v`
Expected: all PASS.

- [ ] **Step 4: Run the full test suite (catch regressions)**

Run: `cd python && uv run pytest -q`
Expected: no new failures attributable to mem0.

- [ ] **Step 5: Lint/format from repo root**

Run: `./python/.venv/bin/pre-commit run --all-files`
Expected: hooks pass (fix any formatting the hooks rewrite, then re-stage).

- [ ] **Step 6: Commit any lint fixes**

```bash
git add -A
git commit -m "chore(mem0): lint/format pass"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** D1 read-only (no write commands) ✓ Task 13-14; D2 flat single scope ✓ Task 2/5/6; D3 `<id>.json` + cat full JSON ✓ Task 6/7/13; D4 search command ✓ Task 10/14; D5 grep content-only ✓ Task 7/14; D6 index cache like langfuse ✓ Task 6; D7 `SUPPORTS_SNAPSHOT=False`/`fingerprint None` ✓ Task 12; D8 history/aggregate deferred (not in any task) ✓; D9 multi-entity → ValidationError ✓ Task 2. §5 file structure ✓ across tasks. §8 tests mirror src ✓ each task. Registry/types/pyproject wiring ✓ Task 1.
- **Type consistency:** `scope_filter`/`scope_kind` (Task 2) used in Tasks 6/10; `Mem0Scope.level`/`memory_id` (Task 5) used in Tasks 6/7/8; `read`/`read_content`/`read_content_stream` (Task 7/14) used in Tasks 13/14; `search_memories_rendered` (Task 10) used in Task 14; `get_all_memories`/`get_memory`/`search_memories` (Task 4) used in Tasks 6/7/10. Consistent.
- **Out of scope:** write ops, `history`, aggregate `memories.jsonl`, entity-rooted tree, TypeScript, snapshot — intentionally excluded.
