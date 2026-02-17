"""STT platform for JetAssist.

Registers as a HA Speech-to-Text provider.
Proxies audio to the JetAssist STT API.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
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
    """Set up JetAssist STT from config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    async_add_entities([JetHomeCloudSTT(api, entry.entry_id)])


class JetHomeCloudSTT(SpeechToTextEntity):
    """JetAssist STT provider for HA."""

    _attr_name = "JetAssist STT"

    def __init__(self, api: Any, entry_id: str) -> None:
        """Initialize."""
        self._api = api
        self._attr_unique_id = f"{DOMAIN}_stt_{entry_id}"

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
    def supported_formats(self) -> list[AudioFormats]:
        """Return supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(self, metadata: SpeechMetadata, stream) -> SpeechResult:
        """Process audio stream and return transcription."""
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk

        try:
            # POST to cloud STT API
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self._api.endpoint}/api/v1/stt/transcribe",
                    headers=self._api._headers,
                    params={
                        "language": metadata.language,
                        "provider": "openai",  # default; configurable later
                    },
                    data={"file": audio_data},
                ) as resp,
            ):
                if resp.status == 200:
                    data = await resp.json()
                    return SpeechResult(
                        text=data.get("text", ""),
                        result=SpeechResultState.SUCCESS,
                    )
                _LOGGER.error("STT API error: %s", resp.status)
                return SpeechResult(text="", result=SpeechResultState.ERROR)
        except Exception as exc:
            _LOGGER.error("STT processing error: %s", exc)
            return SpeechResult(text="", result=SpeechResultState.ERROR)
