from korea_power_torque import (
    KoreaPowerConsensus,
    apply_hp_torque,
    cc_bucket,
    extract_hp_from_text,
    extract_hp_torque_from_payload,
    extract_nm_from_text,
    fuel_bucket,
    thin_row_to_payload_stub,
)


def test_extract_hp_malyeok():
    assert extract_hp_from_text("2.0 케어플러스 164마력") == 164
    assert extract_hp_from_text("Sonata (180)hp") == 180
    assert extract_hp_from_text("2.0 GDI 150 hp") == 150
    assert extract_hp_from_text("LF 2014") is None


def test_extract_nm_kgm_and_nm():
    assert extract_nm_from_text("토크 26.5kg.m") == 260
    assert extract_nm_from_text("260 N·m") == 260
    assert extract_nm_from_text("319Nm") == 319


def test_cc_and_fuel_buckets():
    assert cc_bucket(1998) == 2000
    assert cc_bucket(1591) == 1600
    assert fuel_bucket("가솔린") == "gas"
    assert fuel_bucket("디젤") == "diesel"
    assert fuel_bucket("가솔린+전기") == "hybrid"


def test_payload_extract_prefers_stored_fields():
    hp, nm, src = extract_hp_torque_from_payload(
        {"power": "201", "torque_nm": 365, "generation": "150마력"}
    )
    assert hp == 201
    assert nm == 365
    assert src == "listing_field"


def test_apply_writes_inner_and_spec_clean():
    payload = {"data": {"mark": "Hyundai", "spec_clean": {}}}
    assert apply_hp_torque(payload, hp=180, nm=265, source="peer_year") is True
    assert payload["power"] == "180"
    assert payload["data"]["power_hp"] == 180
    assert payload["data"]["torque_nm"] == 265
    assert payload["data"]["spec_clean"]["power_hp"] == 180
    assert payload["data"]["power_source"] == "peer_year"


def _obs(mark, model, cc, fuel, year, hp=None, nm=None, generation="", turbo_trim=""):
    return {
        "mark": mark,
        "model": model,
        "displacement_cc": cc,
        "fuel_type": fuel,
        "year": year,
        "generation": generation,
        "trim_name": turbo_trim,
        "power_hp": hp,
        "torque_nm": nm,
    }


def test_peer_year_majority_fills_missing():
    table = KoreaPowerConsensus()
    for _ in range(6):
        table.add_observation(_obs("Hyundai", "Sonata", 1999, "가솔린", 2018, 163, 196), hp=163, nm=196)
    table.add_observation(_obs("Hyundai", "Sonata", 1999, "가솔린", 2018, 999, 196), hp=999, nm=196)
    hit = table.resolve(_obs("Hyundai", "Sonata", 1998, "gasoline", 2018))
    assert hit.hp == 163
    assert hit.nm == 196
    assert hit.source in {"peer_year", "peer_generation"}


def test_conflict_without_majority_is_skipped():
    table = KoreaPowerConsensus()
    for _ in range(4):
        table.add_observation(_obs("RideAuto", "Phantom", 1600, "가솔린", 2020, 180), hp=180)
    for _ in range(4):
        table.add_observation(_obs("RideAuto", "Phantom", 1600, "가솔린", 2020, 136), hp=136)
    hit = table.resolve(_obs("RideAuto", "Phantom", 1591, "gasoline", 2020))
    assert hit.hp is None


def test_near_year_only_when_neighbours_agree():
    table = KoreaPowerConsensus()
    for _ in range(5):
        table.add_observation(_obs("Hyundai", "Tucson", 2000, "디젤", 2017, 186, 400), hp=186, nm=400)
    for _ in range(5):
        table.add_observation(_obs("Hyundai", "Tucson", 2000, "디젤", 2019, 186, 400), hp=186, nm=400)
    hit = table.resolve(_obs("Hyundai", "Tucson", 1995, "diesel", 2018))
    assert hit.hp == 186
    assert hit.nm == 400
    assert hit.source == "peer_year_near"


def test_motor_code_single_observation_is_enough():
    table = KoreaPowerConsensus()
    table.add_observation(
        {**_obs("Hyundai", "Sonata", 1999, "가솔린", 2018, 164), "motor_code": "G4NA"},
        hp=164,
    )
    hit = table.resolve(
        {**_obs("Hyundai", "Avante", 1999, "gasoline", 2014), "motor_code": "G4NA"}
    )
    assert hit.hp == 164
    assert hit.source == "peer_motor"


def test_motor_code_fills_other_models():
    table = KoreaPowerConsensus()
    for _ in range(5):
        table.add_observation(
            {**_obs("Hyundai", "Sonata", 1999, "가솔린", 2018, 164, 196), "motor_code": "G4NA"},
            hp=164,
            nm=196,
        )
    hit = table.resolve(
        {**_obs("Hyundai", "Avante", 1999, "gasoline", 2016), "motor_code": "G4NA"}
    )
    assert hit.hp == 164
    assert hit.nm == 196
    assert hit.source == "peer_motor"


def test_family_unanimous_fills_other_years():
    table = KoreaPowerConsensus()
    for year in (2016, 2017, 2018):
        table.add_observation(_obs("RideAuto", "Comet", 2000, "가솔린", year, 150, 196), hp=150, nm=196)
    hit = table.resolve(_obs("RideAuto", "Comet", 1999, "gasoline", 2019))
    assert hit.hp == 150
    assert hit.nm == 196
    assert hit.source == "peer_family"


def test_year_from_year_month_when_year_missing():
    table = KoreaPowerConsensus()
    assert table.family_parts({"mark": "Hyundai", "model": "Sonata", "displacement_cc": 2000, "fuel_type": "gasoline", "year_month": 201803}) is not None


def test_thin_stub_roundtrip_keeps_family():
    row = {
        "mark": "현대",
        "model": "쏘나타",
        "encar_model_group": "쏘나타",
        "generation": "DN8",
        "trim_name": "2.0",
        "fuel_type": "가솔린",
        "displacement_cc": 1999,
        "year": 2020,
        "power_hp": None,
        "torque_nm": None,
    }
    stub = thin_row_to_payload_stub(row)
    table = KoreaPowerConsensus()
    parts = table.family_parts(stub)
    assert parts is not None
    fk, _nk, _gk = parts
    assert fk[0] == "hyundai"
    assert fk[1] == "sonata"
    assert fk[2] == 2000
    assert fk[3] == "gas"
    assert fk[4] == 2020
