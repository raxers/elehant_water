"""Tests for the Elehant config flow."""

from unittest.mock import patch

from homeassistant.components.bluetooth import async_get_advertisement_callback
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elehant_water.const import DOMAIN

from . import (
    GAS_ADDRESS,
    GAS_SERVICE_INFO,
    SVD15_ADDRESS,
    SVD15_PAYLOAD,
    WATER_ADDRESS,
    WATER_B1_SERVICE_INFO,
    WATER_SERVICE_INFO,
    make_service_info,
)

PATCH_SETUP_ENTRY = "custom_components.elehant_water.async_setup_entry"
PATCH_DISCOVERED = (
    "custom_components.elehant_water.config_flow.async_discovered_service_info"
)


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery of a meter via bluetooth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=WATER_SERVICE_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": "СВД-15 9960"}

    with patch(PATCH_SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "СВД-15 9960"
    assert result["data"] == {}
    assert result["result"].unique_id == WATER_ADDRESS


async def test_bluetooth_discovery_history_packet(hass: HomeAssistant) -> None:
    """Test discovery from a packet without readings, e.g. consumption history."""
    payload = bytearray(SVD15_PAYLOAD)
    payload[3] = 8
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=make_service_info(SVD15_ADDRESS, bytes(payload)),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {"name": "СВД-15 12345"}


async def test_bluetooth_discovery_not_supported(hass: HomeAssistant) -> None:
    """Test that the constant B1 packets are not offered for setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=WATER_B1_SERVICE_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test discovery of a meter that is already set up."""
    MockConfigEntry(domain=DOMAIN, unique_id=WATER_ADDRESS).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=WATER_SERVICE_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_no_devices(hass: HomeAssistant) -> None:
    """Test the user step when no meters were seen."""
    with patch(PATCH_DISCOVERED, return_value=[WATER_B1_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_pick_device(hass: HomeAssistant) -> None:
    """Test picking one of the discovered meters."""
    with patch(
        PATCH_DISCOVERED,
        return_value=[WATER_SERVICE_INFO, WATER_B1_SERVICE_INFO, GAS_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_ADDRESS].container == {
        WATER_ADDRESS: "СВД-15 9960",
        GAS_ADDRESS: "СГБД-4.0 66051",
    }

    with patch(PATCH_SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: GAS_ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "СГБД-4.0 66051"
    assert result["result"].unique_id == GAS_ADDRESS


async def test_user_skips_configured(hass: HomeAssistant) -> None:
    """Test that configured meters are not offered again."""
    MockConfigEntry(domain=DOMAIN, unique_id=WATER_ADDRESS).add_to_hass(hass)
    with patch(PATCH_DISCOVERED, return_value=[WATER_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_replaces_discovery_flow(hass: HomeAssistant) -> None:
    """Test that the user flow wins over a pending discovery of the same meter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=WATER_SERVICE_INFO
    )
    assert result["type"] is FlowResultType.FORM

    with patch(PATCH_DISCOVERED, return_value=[WATER_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    with patch(PATCH_SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: WATER_ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_rediscovered_after_removal(hass: HomeAssistant) -> None:
    """Test that a removed meter is offered for setup again right away."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=WATER_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async_get_advertisement_callback(hass)(WATER_SERVICE_INFO)
    await hass.async_block_till_done()
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == [WATER_ADDRESS]
