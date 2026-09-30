import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import (
    ConnectorNotConfiguredError,
    UpstreamInvalidResponseError,
    UpstreamUnavailableError,
)
from app.schemas.source_document import NotebookEntry, NotebookSnapshot


class NotebookConnector:
    def __init__(self, settings: Settings) -> None:
        self._api_url = settings.notebook_api_url.rstrip("/")
        self._api_token = settings.notebook_api_token.get_secret_value()
        self._timeout = settings.notebook_timeout_seconds

    def fetch_entries(self) -> list[NotebookEntry]:
        if not self._api_url or not self._api_token:
            raise ConnectorNotConfiguredError("日序连接器尚未配置。")

        try:
            response = httpx.get(
                f"{self._api_url}/internal/v1/entries",
                params={"kind": "note"},
                headers={"Authorization": f"Bearer {self._api_token}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstreamUnavailableError("暂时无法连接日序，请稍后重试。") from exc

        try:
            return NotebookSnapshot.model_validate(response.json()).items
        except (ValueError, ValidationError) as exc:
            raise UpstreamInvalidResponseError("日序返回了无法识别的数据。") from exc


def get_notebook_connector() -> NotebookConnector:
    return NotebookConnector(get_settings())
