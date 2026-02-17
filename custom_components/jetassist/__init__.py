"""JetAssist integration for Home Assistant.

Provides remote access (tunnel), cloud backups, and AI-powered
voice/conversation services.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JetHomeCloudAPI
from .const import DOMAIN
from .tunnel import TunnelClient

_LOGGER = logging.getLogger(__name__)

# v1 platforms: backup only. v2 will add: STT, TTS, CONVERSATION
PLATFORMS: list[Platform] = [Platform.BACKUP]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up JetAssist from a config entry."""
    session = async_get_clientsession(hass)
    api = JetHomeCloudAPI(
        endpoint=entry.data["endpoint"],
        token=entry.data["api_token"],
        session=session,
    )

    # Verify connection
    if not await api.ping():
        _LOGGER.error("Cannot connect to JetAssist")
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
    }

    # Start tunnel if enabled
    if entry.data.get("tunnel_enabled", True):
        tunnel = TunnelClient(
            server_url=entry.data.get("tunnel_url", f"wss://tun.{_get_domain(entry)}/ws/tunnel"),
            token=entry.data["api_token"],
            local_port=entry.data.get("local_port", 8123),
        )
        hass.data[DOMAIN][entry.entry_id]["tunnel"] = tunnel

        # Run tunnel in background
        entry.async_on_unload(tunnel.stop)
        hass.async_create_task(tunnel.connect())
        _LOGGER.info("JetAssist tunnel started")

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("JetAssist integration set up successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload JetAssist config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        tunnel = data.get("tunnel")
        if tunnel:
            await tunnel.stop()
            _LOGGER.info("JetAssist tunnel stopped")

    return unload_ok


def _get_domain(entry: ConfigEntry) -> str:
    """Extract domain from endpoint URL."""
    endpoint = entry.data.get("endpoint", "https://api.jethome.cloud")
    # https://api.jethome.cloud -> jethome.cloud
    try:
        from urllib.parse import urlparse

        parsed = urlparse(endpoint)
        host = parsed.hostname or "jethome.cloud"
        parts = host.split(".")
        if len(parts) > 2:
            return ".".join(parts[1:])
        return host
    except Exception:
        return "jethome.cloud"
