from apps.asset_library.input_characterization import (
    characterize_input,
)
from apps.asset_library.raw_source import RawSource


def test_characterize_json_input():
    source = RawSource(
        data=b'{"name": "Example", "type": "club"}',
        locator="https://example.test/data",
    )

    characteristics = characterize_input(source)

    assert characteristics.representation == "structured"
    assert characteristics.media_type == "application/json"
    assert characteristics.encoding == "utf-8"

    print("JSON CHARACTERIZATION")
    print(characteristics)