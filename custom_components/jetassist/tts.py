"""TTS platform for JetAssist.

Registers as a HA Text-to-Speech provider.
Proxies text to the JetAssist TTS API.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up JetAssist TTS from config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    async_add_entities([JetHomeCloudTTS(api, entry.entry_id)])


class JetHomeCloudTTS(TextToSpeechEntity):
    """JetAssist TTS provider for HA."""

    _attr_name = "JetAssist TTS"

    def __init__(self, api: Any, entry_id: str) -> None:
        """Initialize."""
        self._api = api
        self._attr_unique_id = f"{DOMAIN}_tts_{entry_id}"

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return [
            "ru",
            "en",
            "de",
            "fr",
            "es",
            "it",
            "pt",
            "nl",
            "pl",
            "uk",
            "zh",
            "ja",
            "ko",
            "ar",
            "tr",
            "sv",
        ]

    @property
    def default_language(self) -> str:
        """Return default language."""
        return "ru"

    async def async_get_tts_audio(self, message: str, language: str, options: dict | None = None) -> tuple[str, bytes]:
        """Get TTS audio from JetAssist."""
        try:
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self._api.endpoint}/api/v1/tts/synthesize",
                    headers=self._api._headers,
                    json={
                        "text": message,
                        "language": language,
                        "voice": (options or {}).get("voice", "default"),
                    },
                ) as resp,
            ):
                if resp.status == 200:
                    audio = await resp.read()
                    return ("wav", audio)
                _LOGGER.error("TTS API error: %s", resp.status)
                return ("wav", b"")
        except Exception as exc:
            _LOGGER.error("TTS processing error: %s", exc)
            return ("wav", b"")
