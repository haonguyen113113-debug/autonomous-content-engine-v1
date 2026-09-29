from apps.asset_library.input_characterization import (
    InputCharacteristics,
)
from apps.asset_library.perception import (
    PerceptionEngine,
)
from apps.asset_library.raw_source import RawSource


class DummyExtractor:
    name = "dummy"

    def can_handle(
        self,
        characteristics: InputCharacteristics,
    ):
        return True

    def extract(
        self,
        source: RawSource,
        characteristics: InputCharacteristics,
    ):
        return [
            {
                "kind": "test",
                "value": "boundary-ok",
                "source_locator": source.locator,
            }
        ]


def test_perception_engine_dispatches_to_extractor():
    source = RawSource(
        data=b"real-source-payload",
        locator="https://example.com/source",
    )

    engine = PerceptionEngine(
        extractors=[DummyExtractor()]
    )

    result = engine.extract(source)

    assert result == [
        {
            "kind": "test",
            "value": "boundary-ok",
            "source_locator": "https://example.com/source",
        }
    ]