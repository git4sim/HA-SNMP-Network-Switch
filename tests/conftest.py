"""Test harness: stub out Home Assistant, voluptuous and pysnmp.

The integration is exercised without a running HA or SNMP stack. Unknown
names imported from a stubbed module resolve to a permissive dummy class.
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class _Meta(type):
    def __getattr__(cls, name):  # enum-style access, e.g. SensorDeviceClass.ENUM
        if name.startswith("__"):
            raise AttributeError(name)
        return name


class _Dummy(metaclass=_Meta):
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs

    def __class_getitem__(cls, item):  # CoordinatorEntity[SomeCoordinator]
        return cls


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (_Dummy,), {})
        setattr(self, name, value)
        return value


def _stub(name: str, **attrs) -> _StubModule:
    mod = _StubModule(name)
    mod.__path__ = []  # behave as a package
    for key, val in attrs.items():
        setattr(mod, key, val)
    sys.modules[name] = mod
    return mod


class UpdateFailed(Exception):
    pass


class DataUpdateCoordinator:
    def __init__(self, hass, logger, config_entry=None, name=None, update_interval=None):
        self.config_entry = config_entry
        self.hass, self.name, self.data = hass, name, None
        self.refresh_calls = 0

    def __class_getitem__(cls, item):
        return cls

    async def async_refresh(self):
        self.refresh_calls += 1

    async def async_request_refresh(self):
        self.refresh_calls += 1


class CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    def __class_getitem__(cls, item):
        return cls


for _name in (
    "voluptuous",
    "homeassistant",
    "homeassistant.helpers",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.components.switch",
    "homeassistant.components.text",
    "homeassistant.components.button",
    "pysnmp",
    "pysnmp.hlapi",
    "pysnmp.hlapi.v3arch",
    "pysnmp.hlapi.v3arch.asyncio",
    "pysnmp.proto",
    "pysnmp.proto.rfc1902",
):
    _stub(_name)

_stub(
    "homeassistant.helpers.update_coordinator",
    DataUpdateCoordinator=DataUpdateCoordinator,
    CoordinatorEntity=CoordinatorEntity,
    UpdateFailed=UpdateFailed,
)
sys.modules["homeassistant.const"].CONF_HOST = "host"
sys.modules["homeassistant.const"].CONF_NAME = "name"
sys.modules["homeassistant.const"].CONF_PORT = "port"


def run(coro):
    """Run a coroutine to completion (no pytest-asyncio dependency)."""
    return asyncio.run(coro)
