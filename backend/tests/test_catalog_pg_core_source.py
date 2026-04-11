"""cars.source NOT NULL: row_to_car_fields must never omit source (postgres_catalog_sync path)."""

from catalog_pg_core import row_to_car_fields


def test_row_to_car_fields_defaults_encar_when_data_has_no_source():
    payload = {"data": {"mark": "벤츠", "model": "S", "id": "41591957"}}
    f = row_to_car_fields("41591957", payload)
    assert f["source"] == "encar"


def test_row_to_car_fields_dongchedi_prefix_without_inner_source():
    cid = "dongchedi-abc-1"
    payload = {"data": {"mark": "X", "model": "Y", "id": cid}}
    f = row_to_car_fields(cid, payload)
    assert f["source"] == "dongchedi"


def test_row_to_car_fields_respects_inner_source():
    payload = {"data": {"mark": "M", "model": "N", "source": "dongchedi"}}
    f = row_to_car_fields("x-1", payload)
    assert f["source"] == "dongchedi"
