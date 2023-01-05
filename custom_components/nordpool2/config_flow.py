"""Adds config flow for nordpool."""
import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.template import Template

from . import DOMAIN, REGIONS, CURRENCY_TO_CENTS

regions = sorted(REGIONS)
currencies = sorted(CURRENCY_TO_CENTS.keys())

_LOGGER = logging.getLogger(__name__)


class NordpoolFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nordpool."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(
        self, user_input=None
    ):  # pylint: disable=dangerous-default-value
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            return self.async_create_entry(title="Nordpool", data=user_input)

        data_schema = {
            vol.Optional("region", default="SE3"): vol.In(regions),
            vol.Optional("currency", default="SEK"): vol.In(currencies),
        }

        placeholders = {
            "region": regions,
            "currency": currencies,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            description_placeholders=placeholders,
            errors=self._errors,
        )

    async def async_step_import(self, user_input):  # pylint: disable=unused-argument
        """Import a config entry.
        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        return self.async_create_entry(title="configuration.yaml", data={})
