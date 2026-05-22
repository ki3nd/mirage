from typing import Any

from mirage.accessor.base import Accessor
from mirage.resource.chromadb.config import ChromaDBConfig


class ChromaDBAccessor(Accessor):

    def __init__(self, config: ChromaDBConfig) -> None:
        self.config = config
        self._client: Any | None = None
        self._collection: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._create_client()
        return self._client

    @property
    def collection(self) -> Any:
        if self._collection is None:
            self._collection = self.client.get_collection(
                self.config.collection_name)
        return self._collection

    def _create_client(self) -> Any:
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            raise ImportError(
                "ChromaDB resource requires the 'chromadb' extra. "
                "Install with: pip install mirage-ai[chromadb]") from exc

        settings = Settings()
        if self.config.api_key:
            settings = Settings(
                chroma_client_auth_provider=(
                    "chromadb.auth.token_authn.TokenAuthClientProvider"),
                chroma_client_auth_credentials=self.config.api_key,
            )
        return chromadb.HttpClient(
            host=self._host(),
            port=self.config.port,
            ssl=self.config.ssl,
            settings=settings,
        )

    def _host(self) -> str:
        if not self.config.prefix:
            return self.config.host
        if self.config.host.startswith(("http://", "https://")):
            return self.config.host.rstrip("/") + self.config.prefix
        scheme = "https" if self.config.ssl else "http"
        return f"{scheme}://{self.config.host.rstrip('/')}{self.config.prefix}"
