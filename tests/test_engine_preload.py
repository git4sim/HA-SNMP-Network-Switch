"""The shared SnmpEngine preloads pysnmp's MIBs off the event loop."""
from __future__ import annotations

import pytest

from custom_components.snmp_switch import snmp_client


class FakeBuilder:
    def __init__(self, missing=()):
        self.loaded, self.missing = [], set(missing)

    def load_modules(self, *names):
        for name in names:
            if name in self.missing:
                raise RuntimeError(f"MIB {name} not found")
            self.loaded.append(name)


class FakeEngine:
    builder = FakeBuilder()

    def get_mib_builder(self):
        return self.builder


@pytest.fixture(autouse=True)
def fresh_engine(monkeypatch):
    monkeypatch.setattr(snmp_client, "_ENGINE", None)
    monkeypatch.setattr(snmp_client, "SnmpEngine", FakeEngine)
    FakeEngine.builder = FakeBuilder()


def test_preloads_every_listed_module():
    snmp_client._get_or_create_engine()
    assert FakeEngine.builder.loaded == list(snmp_client._PRELOAD_MIBS)


def test_covers_the_modules_that_block_the_loop():
    # What pysnmp otherwise opens from disk during the first request / v3 use.
    needed = {"PYSNMP-SOURCE-MIB", "PYSNMP-USM-MIB", "SNMPv2-TM", "__SNMPv2-MIB", "__PYSNMP-USM-MIB"}
    assert needed <= set(snmp_client._PRELOAD_MIBS)


def test_if_mib_is_not_requested():
    # pysnmp doesn't ship IF-MIB; requesting it raised and (when it shared one
    # load call with the others) aborted the whole preload.
    assert "IF-MIB" not in snmp_client._PRELOAD_MIBS


def test_a_missing_module_does_not_stop_the_rest():
    FakeEngine.builder = FakeBuilder(missing={"SNMPv2-TM", "__PYSNMP-USM-MIB"})
    snmp_client._get_or_create_engine()
    expected = [m for m in snmp_client._PRELOAD_MIBS if m not in {"SNMPv2-TM", "__PYSNMP-USM-MIB"}]
    assert FakeEngine.builder.loaded == expected


def test_engine_is_created_once():
    first = snmp_client._get_or_create_engine()
    FakeEngine.builder = FakeBuilder()
    assert snmp_client._get_or_create_engine() is first
    assert FakeEngine.builder.loaded == []  # no second preload
