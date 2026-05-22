from mirage.resource.chromadb.config import ChromaDBConfig

__all__ = ["ChromaDBConfig", "ChromaDBResource"]


def __getattr__(name: str):
    if name == "ChromaDBResource":
        from mirage.resource.chromadb.chromadb import ChromaDBResource
        return ChromaDBResource
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
