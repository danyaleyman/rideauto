from pathlib import Path

import pytest

from encar_mapping_lookup import encar_mapping_en_for


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "data" / "encar_mapping.json").is_file(),
    reason="encar_mapping.json not present",
)
def test_encar_mapping_hyundai():
    assert encar_mapping_en_for("mark", "현대") == "Hyundai"
