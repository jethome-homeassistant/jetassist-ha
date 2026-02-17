"""Conversation agent for JetAssist.

Registers as a HA Conversation Agent powered by cloud LLM.
Supports function calling for HA service calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.conversation import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# HA tools for LLM function calling
HA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "call_ha_service",
            "description": "Call a Home Assistant service to control a device",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "service": {"type": "string"},
                    "entity_id": {"type": "string"},
                    "data": {"type": "object"},
                },
                "required": ["domain", "service", "entity_id"],
            },
        },
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Set up conversation agent."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    agent = JetHomeCloudConversationAgent(hass, api, entry.entry_id)
    # Register the agent -- the actual registration depends on HA version
    hass.data[DOMAIN][entry.entry_id]["conversation_agent"] = agent


class JetHomeCloudConversationAgent(AbstractConversationAgent):
    """JetAssist LLM as HA Conversation Agent."""

    def __init__(
        self, hass: HomeAssistant, api: Any, entry_id: str
    ) -> None:
        """Initialize."""
        self.hass = hass
        self._api = api
        self._entry_id = entry_id

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return ["ru", "en", "de", "fr", "es"]

    async def async_process(
        self, user_input: ConversationInput
    ) -> ConversationResult:
        """Process a conversation turn."""
        try:
            # Build messages with device context
            exposed_entities = self._get_exposed_entities()
            messages = [
                {
                    "role": "system",
                    "content": self._build_system_prompt(exposed_entities),
                },
                {"role": "user", "content": user_input.text},
            ]

            # Send to cloud LLM
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._api.endpoint}/api/v1/chat/completions",
                    headers=self._api._headers,
                    json={
                        "messages": messages,
                        "tools": HA_TOOLS,
                        "temperature": 0.7,
                        "max_tokens": 1024,
                    },
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        _LOGGER.error("LLM API error: %s %s", resp.status, error)
                        response = intent.IntentResponse(
                            language=user_input.language
                        )
                        response.async_set_speech(
                            "Sorry, I couldn't process your request."
                        )
                        return ConversationResult(response=response)

                    data = await resp.json()

            # Handle the response
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

            # Execute tool calls if any
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                await self._execute_tool_calls(tool_calls)

            # Build response
            response_text = message.get("content", "")
            response = intent.IntentResponse(language=user_input.language)
            response.async_set_speech(response_text)
            return ConversationResult(response=response)

        except Exception as exc:
            _LOGGER.error("Conversation error: %s", exc)
            response = intent.IntentResponse(language=user_input.language)
            response.async_set_speech(
                "An error occurred while processing your request."
            )
            return ConversationResult(response=response)

    def _get_exposed_entities(self) -> list[dict[str, Any]]:
        """Get entities exposed to voice assistants."""
        entities = []
        for state in self.hass.states.async_all():
            entities.append({
                "entity_id": state.entity_id,
                "friendly_name": state.attributes.get("friendly_name", ""),
                "state": state.state,
                "domain": state.domain,
            })
        # Limit to first 100 entities to keep prompt size manageable
        return entities[:100]

    def _build_system_prompt(self, entities: list[dict[str, Any]]) -> str:
        """Build system prompt with device context."""
        devices_text = "\n".join(
            f"- {e['entity_id']}: {e['friendly_name']} (state: {e['state']})"
            for e in entities
        )
        return (
            "You are a helpful smart home assistant powered by JetAssist.\n"
            "You help the user control their Home Assistant devices.\n\n"
            f"Available devices:\n{devices_text}\n\n"
            "When controlling devices, use the call_ha_service function.\n"
            "Respond in the user's language. Be concise."
        )

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> None:
        """Execute HA service calls from LLM function calls."""
        for call in tool_calls:
            func = call.get("function", {})
            if func.get("name") == "call_ha_service":
                try:
                    args = json.loads(func.get("arguments", "{}"))
                    await self.hass.services.async_call(
                        domain=args["domain"],
                        service=args["service"],
                        service_data={
                            "entity_id": args["entity_id"],
                            **args.get("data", {}),
                        },
                    )
                    _LOGGER.info(
                        "Executed service call: %s.%s for %s",
                        args["domain"],
                        args["service"],
                        args["entity_id"],
                    )
                except Exception as exc:
                    _LOGGER.error("Service call failed: %s", exc)
