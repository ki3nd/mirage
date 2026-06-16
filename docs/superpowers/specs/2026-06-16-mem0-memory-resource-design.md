# mem0 "Memory" resource — design

Date: 2026-06-16
Status: Approved (design), pending spec review
Scope: Python only (`python/`). No TypeScript in this iteration.

## 1. Goal

Add a new **read-only** resource type that mounts a [mem0](https://docs.mem0.ai)
memory store as a virtual filesystem, so AI agents can browse, read, and
semantically search a user's / agent's / run's memories with ordinary
shell-style commands (`ls`, `cat`, `grep`, `find`, `head`, `tail`, `wc`,
`tree`, `stat`, `jq`) plus a dedicated `search` command.

Registry name: `mem0`. `ResourceName.MEM0 = "mem0"`.

Mirrors the existing `langfuse` / `dify` remote read-only resources in layout,
caching, and command wiring.

## 2. Key facts about mem0 (verified against the live API)

- SDK: `mem0ai` (installed as the `mem0` optional extra). Use
  **`mem0.AsyncMemoryClient`** — async-native, fits mirage's async rule.
- Auth: `AsyncMemoryClient(api_key=..., host="https://api.mem0.ai")`.
  `org_id` / `project_id` are resolved from the API key server-side.
- **The constructor calls `_validate_api_key()` which does a blocking
  `requests.get("/v1/ping/")`.** It does not break the event loop, but it
  blocks and requires network + a valid key at construction time. → We build
  the client **lazily** (first op), so mounting stays cheap and offline-safe.
- Entity ids (`user_id`, `agent_id`, `app_id`, `run_id`) must be passed
  **inside `filters`**; top-level entity kwargs raise.
  `ENTITY_PARAMS = {user_id, agent_id, app_id, run_id}`.
- Relevant methods (all have async variants):
  - `get_all(GetAllMemoryOptions(filters, page, page_size, start_date,
    end_date, categories))` → `{count, next, previous, results: [...]}`.
  - `search(query, SearchMemoryOptions(filters, top_k, rerank, threshold,
    categories))` → `{results: [...]}` (each result has a `score`).
  - `get(memory_id)`, `history(memory_id)`, `users()`.
- `users()` → `{results: [{id, name, created_at, type, ...}],
  total_users, total_agents, total_apps, total_runs}` where
  `type ∈ {user, agent, app, run}` and `name` is the entity id used in filters.
- Memory object fields: `id, memory, user_id, agent_id, run_id?, metadata,
  categories, created_at, updated_at, expiration_date, structured_attributes`,
  plus `score` on search results.

### 2.1 Storage model note (verified)

In practice each memory is attributed to a **single** entity: a memory added
with both `user_id` and `agent_id` is split, so `get_all(filters={user_id})`
returns rows with `agent_id=None` and vice-versa. A combined `AND` of two
entity ids returns 0 against such data. This is why the VFS uses a **single
configured scope per mount** rather than a combined-filter tree.

## 3. Decisions

| # | Decision |
|---|----------|
| D1 | **Read-only.** No add/update/delete in this iteration. |
| D2 | **Flat tree, single configured scope** (single-tenant mount). Config carries exactly one of `user_id` / `agent_id` / `run_id`. |
| D3 | Each memory is a file `<memory_id>.json`; `cat` returns the full memory JSON (pretty-printed). |
| D4 | **`search`** is a dedicated command (mirrors dify) → `client.search(query, filters=scope)`, ranked by `score`. It calls the mem0 search API directly (no cache). |
| D5 | **`grep` matches content only.** It lists memories via `get_all` and filters **client-side** over the `memory` text only — never metadata (id, categories, timestamps, `structured_attributes`). Implemented by wiring grep with a **content-projection reader** that yields `m["memory"]`. This is a deliberate, documented divergence from byte-identical `cat`/`grep`. |
| D6 | Index cache used exactly like langfuse `readdir`: cache-first, API-second; one `virtual_key` (the mount prefix, since the tree is flat). `cat`/`stat` reuse primed entries. |
| D7 | `SUPPORTS_SNAPSHOT = False` (live-only, like langfuse/dify); `fingerprint → None`. |
| D8 | Defer `history(memory_id)` and any aggregate `memories.jsonl` view to a later iteration. |
| D9 | If config sets more than one entity id → **validation error** (clear, since combined filters return nothing). |

## 4. VFS layout

```
<mount>/                         # scope = {user_id: "alex"}  (example)
├── 6d1ba0fc-….json              # cat → full memory JSON
├── 4d221f85-….json
└── …                            # one file per memory in get_all(filters=scope)
```

- `ls <mount>/` → `get_all(filters=scope, page_size=default_page_size)`,
  paginated and concatenated, one `<id>.json` per memory.
- `cat <mount>/<id>.json` → full memory JSON.
- `grep PATTERN <mount>/` → content-only match (see D5).
- `search "<query>" <mount>/` → semantic search within the scope.
- Hidden paths (`.`-prefixed) → `ENOENT`, mirroring langfuse.

## 5. File structure (mirror langfuse/dify 1:1)

```
mirage/resource/mem0/
├── __init__.py            # re-export Mem0Resource, Mem0Config
├── config.py             # Mem0Config
├── mem0.py               # Mem0Resource(BaseResource)
└── prompt.py             # PROMPT

mirage/accessor/mem0.py    # Mem0Accessor (lazy AsyncMemoryClient)

mirage/core/mem0/
├── __init__.py
├── _client.py            # thin async fetch helpers: get_all_memories, get_memory, search_memories
├── scope.py              # config scope -> filters dict; path validation
├── readdir.py            # cache-first listing
├── read.py               # read_bytes / read_stream (full JSON); content-projection reader for grep
├── stat.py
├── search.py             # semantic search -> ranked bytes (dify-style records_to_bytes)
└── glob.py               # resolve_glob over the flat listing

mirage/ops/mem0/
├── __init__.py           # OPS = [readdir, read, stat]
├── readdir.py            # @op("readdir", resource="mem0")
├── read.py
└── stat.py

mirage/commands/builtin/mem0/
├── __init__.py           # COMMANDS = [...]
├── ls.py  cat.py  find.py  grep.py  head.py  tail.py  wc.py
├── tree.py  stat.py  jq.py
└── search.py             # dedicated semantic search command
```

Wiring:
- `mirage/types.py`: add `MEM0 = "mem0"` to `ResourceName`.
- `mirage/resource/registry.py`: add
  `"mem0": ResourceEntry("mirage.resource.mem0:Mem0Resource", "mirage.resource.mem0:Mem0Config")`.
- `pyproject.toml`: `mem0` extra already added; also add `mirage-ai[mem0]` to
  the `all` meta-extra.

## 6. Components

### 6.1 `Mem0Config`

```python
class Mem0Config(BaseModel):
    api_key: SecretStr
    host: str = "https://api.mem0.ai"
    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    default_page_size: int = 100
    default_search_limit: int = 10   # top_k

    # validator: exactly one of user_id/agent_id/run_id must be set (D9)
    # property scope_filter -> {"<entity>_id": value}
    # property scope_kind   -> "user" | "agent" | "run"
```

### 6.2 `Mem0Accessor`

```python
class Mem0Accessor(Accessor):
    def __init__(self, config: Mem0Config) -> None:
        self.config = config
        self._client = None          # lazy

    @property
    def client(self) -> AsyncMemoryClient:
        if self._client is None:
            self._client = AsyncMemoryClient(
                api_key=reveal_secret(self.config.api_key),
                host=self.config.host,
            )
        return self._client
```

Lazy because the constructor blocks on `_validate_api_key()` (§2).

### 6.3 `Mem0Resource`

Mirrors `LangfuseResource`: registers `COMMANDS` and `OPS`, implements
`resolve_glob`, `fingerprint → None`, `get_state`/`load_state` via
`config_state` with `api_key` redacted.

### 6.4 Core caching (`readdir.py`)

Same shape as langfuse `_readdir_*`:

```python
async def readdir(accessor, path, index):
    virtual_key = path.prefix or "/"
    if index is not None:
        listing = await index.list_dir(virtual_key)
        if listing.entries is not None:
            return listing.entries
    resp = await get_all_memories(accessor.client,
                                  filters=accessor.config.scope_filter,
                                  page_size=accessor.config.default_page_size)
    entries, names = [], []
    for m in resp["results"]:
        filename = f"{m['id']}.json"
        body = _json_bytes(m)
        entry = IndexEntry(id=m["id"], name=m["id"],
                           resource_type="mem0/memory", vfs_name=filename,
                           size=len(body), extra={"memory": m})  # prime cat/grep
        entries.append((filename, entry))
        names.append(f"{path.prefix}/{filename}")
    if index is not None:
        await index.set_dir(virtual_key, entries)
    return names
```

Priming `extra={"memory": m}` lets `cat`/`stat`/`grep` reuse the listing within
the TTL window without re-calling `get_all`/`get`.

### 6.5 `read.py`

- `read_bytes(path)` / `read_stream(path)` → full memory JSON. Resolve the
  memory from the primed index entry if present, else `get(memory_id)`.
- `read_content_bytes(path)` → `m["memory"]` only (used by `grep`, D5).

### 6.6 `grep` wiring

```python
@command("grep", resource="mem0", spec=SPECS["grep"])
async def grep(accessor, paths, *texts, index=None, **flags):
    paths = await resolve_glob(accessor, paths, index)
    return await generic_grep(
        paths, texts, flags,
        readdir=readdir, stat=stat,
        read_bytes=read_content_bytes,           # content-only (D5)
        read_stream=partial(read_content_stream, index=index),
        accessor=accessor, index=index,
    )
```

`cat`/`jq` use the full-JSON readers; only `grep` uses the content readers.

### 6.7 `search.py`

```python
async def search_memories(accessor, query, *, top_k, threshold):
    resp = await accessor.client.search(
        query,
        options=SearchMemoryOptions(filters=accessor.config.scope_filter,
                                    top_k=top_k, threshold=threshold))
    # render each result as "<id>.json:<score>\n<memory>", dify-style
```

The `search` command parses query + `top_k`/`threshold` flags via `FlagView`
and the command spec, mirroring dify's `search` command.

## 7. Error handling

- Invalid / hidden / non-existent paths → `enoent`, mirroring langfuse.
- mem0 API errors propagate (never silently swallowed). Auth/quota/network
  errors from the SDK surface to the caller.
- Config with zero or ≥2 entity ids → pydantic `ValidationError` at build time.

## 8. Testing (mirror src 1:1, no network)

Mock `Mem0Accessor.client` with a fake `AsyncMemoryClient` exposing
`get_all` / `get` / `search` coroutines returning fixture dicts.

- `tests/resource/mem0/test_mem0.py` — registration, state, scope validation.
- `tests/core/mem0/test_scope.py` — single-entity validation, `scope_filter`.
- `tests/core/mem0/test_readdir.py` — cache miss → `get_all`; cache hit → no
  second call; listing == returned names invariant.
- `tests/core/mem0/test_read.py` — full JSON vs content-only projection.
- `tests/core/mem0/test_search.py` — query/flags → `search` call, ranked output.
- `tests/commands/builtin/mem0/` — `ls`, `cat`, `grep` (content-only matches,
  not metadata), `search`, `find`, `head`, `tail`, `wc`, `tree`, `stat`, `jq`.

Follow the monkeypatch rule from CLAUDE.md when intercepting command-module
helpers (`monkeypatch.setitem(cat.__wrapped__.__globals__, ...)`).

## 9. Out of scope (later iterations)

- Write ops (`add` / `delete` / `update`).
- `history(memory_id)` views and aggregate `memories.jsonl`.
- Multi-scope / entity-rooted browsing tree.
- TypeScript parity (mem0 has a JS SDK; mirror later).
- Snapshot support (`SUPPORTS_SNAPSHOT` stays `False`).
