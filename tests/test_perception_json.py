import pytest

from apps.asset_library.perception import (
    PerceptionEngine,
    UnsupportedSourceError,
)
from apps.asset_library.raw_source import RawSource


def test_engine_rejects_unimplemented_json_strategy():
    source = RawSource(
        data=b'{"name": "Example", "type": "club"}',
        locator="https://example.test/data",
    )

    engine = PerceptionEngine(
        extractors=[],
    )

    with pytest.raises(UnsupportedSourceError):
        engine.extract(source)

    print("JSON REACHED PERCEPTION ENGINE")