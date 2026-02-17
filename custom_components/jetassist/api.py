"""Async client for JetAssist API."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class JetHomeCloudAPI:
    """Async client to JetAssist backend."""

    def __init__(
        self,
        endpoint: str,
        token: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "JetHomeCloud-HA/0.1.0",
        }

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def ping(self) -> bool:
        """Check cloud connectivity."""
        try:
            async with self.session.get(
                f"{self.endpoint}/api/v1/ping",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return resp.status == 200
        except Exception as exc:
            _LOGGER.debug("Ping failed: %s", exc)
            return False

    async def presign_upload(
        self,
        filename: str,
        size: int,
        md5: str | None = None,
    ) -> dict[str, Any]:
        """Get presigned URL for backup upload."""
        async with self.session.post(
            f"{self.endpoint}/api/v1/backups/presign-upload",
            headers=self._headers,
            json={"filename": filename, "size": size, "md5": md5},
        ) as resp:
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()
            return data

    async def presign_download(self, backup_id: str) -> dict[str, Any]:
        """Get presigned URL for backup download."""
        async with self.session.post(
            f"{self.endpoint}/api/v1/backups/{backup_id}/presign-download",
            headers=self._headers,
        ) as resp:
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()
            return data

    async def list_backups(self) -> list[dict[str, Any]]:
        """List all cloud backups."""
        async with self.session.get(
            f"{self.endpoint}/api/v1/backups",
            headers=self._headers,
        ) as resp:
            resp.raise_for_status()
            data: list[dict[str, Any]] = await resp.json()
            return data

    async def delete_backup(self, backup_id: str) -> None:
        """Delete a backup."""
        async with self.session.delete(
            f"{self.endpoint}/api/v1/backups/{backup_id}",
            headers=self._headers,
        ) as resp:
            resp.raise_for_status()

    async def get_providers(self) -> dict[str, Any]:
        """Get available STT/TTS/LLM providers (MVP v2)."""
        async with self.session.get(
            f"{self.endpoint}/api/v1/providers",
            headers=self._headers,
        ) as resp:
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()
            return data
