"""The base every LK IHC entity is built on."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import DOMAIN
from .controller import IHCConnection
from .project import Product, Resource


def area_for_group(hass: HomeAssistant, group: str) -> str:
    """Name the area an IHC group belongs in, preferring one the installation already has."""
    registry = ar.async_get(hass)
    area = registry.async_get_area_by_name(group)
    if area is None:
        aliased = registry.async_get_areas_by_alias(group)
        area = aliased[0] if len(aliased) == 1 else registry.async_get_area(slugify(group))
    return area.name if area else group


class IHCEntity(Entity):
    """An entity for one IHC resource, belonging to the device of its product."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        connection: IHCConnection,
        product: Product,
        resource: Resource,
        *,
        primary: bool = False,
        controller_device_id: str = "",
    ) -> None:
        """Set up naming, identity and the device this entity belongs to."""
        self._connection = connection
        self._product = product
        self._resource = resource
        serial = connection.serial_number
        self._attr_unique_id = f"{serial}-{resource.ihc_id}"
        self._attr_entity_registry_enabled_default = resource.enabled_default
        if resource.icon:
            self._attr_icon = resource.icon
        if primary or not resource.name:
            self._attr_name = None
        else:
            self._attr_name = resource.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{serial}-{product.product_id}")},
            name=product.device_name,
            manufacturer="Schneider Electric",
            model=product.model,
            model_id=product.model_id or None,
            suggested_area=product.group or None,
            via_device_id=controller_device_id,
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the product's device info with the matching suggested area."""
        info = self._attr_device_info
        if info is None or self.hass is None or not self._product.group:
            return info

        info.update(
            {"suggested_area": area_for_group(self.hass, self._product.group)}
        )
        return info

    async def async_added_to_hass(self) -> None:
        """Start listening for values from the controller."""
        await self._connection.async_subscribe(
            self._resource.ihc_id, self._handle_value
        )

    @callback
    def _handle_value(self, value: Any) -> None:
        """Handle a new value from the controller."""
        self._apply_value(value)
        if self.hass is not None:
            self.async_write_ha_state()

    @callback
    def _apply_value(self, value: Any) -> None:
        """Store the value. Each platform decides what its state means."""
        raise NotImplementedError

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose where this entity comes from."""
        attributes = {
            "ihc_id": self._resource.ihc_id,
            "ihc_product": self._product.name,
        }
        if self._product.note:
            attributes["ihc_note"] = self._product.note
        if self._product.position:
            attributes["ihc_position"] = self._product.position
        if self._product.controlled_by:
            attributes["ihc_controlled_by"] = list(self._product.controlled_by)
        if self._product.function_blocks:
            attributes["ihc_function_block"] = list(
                self._product.function_blocks
            )
        return attributes
