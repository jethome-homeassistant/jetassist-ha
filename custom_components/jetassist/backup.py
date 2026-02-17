"""Backup platform for JetAssist.

Implements HA Backup Agent API for cloud backup storage.
Uses presigned S3 URLs for direct upload/download.
"""

from __future__ import annotations

import hashlib
import base64
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

import aiohttp

from homeassistant.components.backup import BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return backup agents."""
    agents: list[BackupAgent] = []
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        api = data.get("api")
        if api:
            agents.append(JetHomeCloudBackupAgent(entry_id, api))
    return agents


class JetHomeCloudBackupAgent(BackupAgent):
    """JetAssist backup agent."""

    domain = DOMAIN
    name = "JetAssist"

    def __init__(self, entry_id: str, api: Any) -> None:
        """Initialize."""
        super().__init__()
        self._entry_id = entry_id
        self._api = api

    @callback
    def async_get_unique_id(self) -> str:
        """Return unique ID."""
        return f"{DOMAIN}_{self._entry_id}"

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup_id: str,
        filename: str,
        size: int,
        **kwargs: Any,
    ) -> None:
        """Upload a backup to JetAssist via presigned S3 URL."""
        _LOGGER.info("Uploading backup %s (%s, %d bytes)", backup_id, filename, size)

        # Calculate MD5
        md5_hash = hashlib.md5()  # noqa: S324
        stream = await open_stream()
        async for chunk in stream:
            md5_hash.update(chunk)
        md5_b64 = base64.b64encode(md5_hash.digest()).decode()

        # Get presigned URL
        try:
            presign = await self._api.presign_upload(
                filename=filename,
                size=size,
                md5=md5_b64,
            )
        except Exception as exc:
            raise BackupAgentError(f"Failed to get upload URL: {exc}") from exc

        # Upload directly to S3
        try:
            stream = await open_stream()
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    presign["url"],
                    headers=presign.get("headers", {}),
                    data=stream,
                    timeout=aiohttp.ClientTimeout(total=43200),
                ) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        raise BackupAgentError(
                            f"Upload failed: {resp.status} {text[:200]}"
                        )
        except BackupAgentError:
            raise
        except Exception as exc:
            raise BackupAgentError(f"Upload error: {exc}") from exc

        _LOGGER.info("Backup %s uploaded successfully", backup_id)

    async def async_list_backups(self, **kwargs: Any) -> list[dict[str, Any]]:
        """List available backups."""
        try:
            return await self._api.list_backups()
        except Exception as exc:
            _LOGGER.error("Failed to list backups: %s", exc)
            return []

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup from JetAssist."""
        _LOGGER.info("Downloading backup %s", backup_id)
        try:
            presign = await self._api.presign_download(backup_id)
        except Exception as exc:
            raise BackupAgentError(f"Failed to get download URL: {exc}") from exc

        async def _stream() -> AsyncIterator[bytes]:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    presign["url"],
                    timeout=aiohttp.ClientTimeout(total=43200),
                ) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.content.iter_chunked(65536):
                        yield chunk

        return _stream()

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup."""
        _LOGGER.info("Deleting backup %s", backup_id)
        try:
            await self._api.delete_backup(backup_id)
        except Exception as exc:
            raise BackupAgentError(f"Failed to delete backup: {exc}") from exc
