"""Config flow for JetAssist integration.

Supports two auth methods:
1. OAuth2 flow (recommended): opens browser -> Authentik login -> auto token
2. Manual API token: user copies token from Authentik settings
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult

from .api import JetHomeCloudAPI
from .const import DEFAULT_ENDPOINT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class JetHomeCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JetAssist."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: choose auth method."""
        if user_input is not None:
            method = user_input.get("auth_method", "token")
            if method == "oauth2":
                return await self.async_step_oauth2()
            return await self.async_step_token()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("endpoint", default=DEFAULT_ENDPOINT): str,
                    vol.Required("auth_method", default="oauth2"): vol.In(
                        {"oauth2": "OAuth2 Login (recommended)", "token": "API Token"}
                    ),
                }
            ),
        )

    async def async_step_oauth2(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle OAuth2 flow.

        Opens browser to Authentik for login, receives token via callback.
        """
        # TODO: implement full OAuth2 PKCE flow with Authentik
        # For now, redirect to manual token as fallback
        _LOGGER.info("OAuth2 flow not yet implemented, falling back to token")
        return await self.async_step_token()

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual API token entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            endpoint = self.context.get("endpoint", DEFAULT_ENDPOINT)
            api = JetHomeCloudAPI(
                endpoint=endpoint,
                token=user_input["api_token"],
            )
            try:
                if await api.ping():
                    return self.async_create_entry(
                        title="JetAssist",
                        data={
                            "endpoint": endpoint,
                            "api_token": user_input["api_token"],
                            "tunnel_enabled": user_input.get("tunnel_enabled", True),
                            "auth_method": "token",
                        },
                    )
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema(
                {
                    vol.Required("api_token"): str,
                    vol.Optional("tunnel_enabled", default=True): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "auth_url": f"https://auth.{DEFAULT_ENDPOINT.split('//')[1].split('/')[0].replace('api.', '')}",
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return JetHomeCloudOptionsFlow(config_entry)


class JetHomeCloudOptionsFlow(OptionsFlow):
    """Handle options flow for JetAssist."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "tunnel_enabled",
                        default=self.config_entry.data.get(
                            "tunnel_enabled", True
                        ),
                    ): bool,
                }
            ),
        )
