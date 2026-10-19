"""Package structure checks: every public export and module imports, and the ClickHouse
classes share ClickHouseClientMixin. Offline (no ClickHouse server needed)."""

import importlib

import pytest

import exness_data_preprocess as edp

PUBLIC_EXPORTS = [
    "ExnessDataProcessor",
    "UpdateResult",
    "CoverageInfo",
    "DryRunResult",
    "PairType",
    "TimeframeType",
    "VariantType",
    "supported_pairs",
    "supported_timeframes",
    "supported_variants",
    "ClickHouseManager",
    "ClickHouseGapDetector",
    "ClickHouseQueryEngine",
    "ClickHouseOHLCGenerator",
    "ClickHouseConnectionError",
    "ClickHouseQueryError",
    "get_clickhouse_client",
]

MODULES = [
    "exness_data_preprocess.clickhouse_base",
    "exness_data_preprocess.clickhouse_client",
    "exness_data_preprocess.clickhouse_gap_detector",
    "exness_data_preprocess.clickhouse_manager",
    "exness_data_preprocess.clickhouse_ohlc_generator",
    "exness_data_preprocess.clickhouse_query_engine",
    "exness_data_preprocess.downloader",
    "exness_data_preprocess.exchanges",
    "exness_data_preprocess.models",
    "exness_data_preprocess.processor",
    "exness_data_preprocess.session_detector",
    "exness_data_preprocess.tick_loader",
]

MIXIN_CLASSES = [
    "ClickHouseManager",
    "ClickHouseGapDetector",
    "ClickHouseQueryEngine",
    "ClickHouseOHLCGenerator",
]


@pytest.mark.parametrize("name", PUBLIC_EXPORTS)
def test_public_export_importable(name):
    assert hasattr(edp, name), f"exness_data_preprocess.{name} is not exported"


@pytest.mark.parametrize("module", MODULES)
def test_module_importable(module):
    importlib.import_module(module)


@pytest.mark.parametrize("name", MIXIN_CLASSES)
def test_clickhouse_class_uses_mixin(name):
    from exness_data_preprocess.clickhouse_base import ClickHouseClientMixin

    cls = getattr(edp, name)
    assert issubclass(cls, ClickHouseClientMixin)
    for attr in ("client", "close", "_init_client"):
        assert hasattr(cls, attr), f"{name} is missing {attr}"
