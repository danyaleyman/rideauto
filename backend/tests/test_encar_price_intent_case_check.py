from scripts.encar_price_intent_case_check import _load_cases, _parse_case_arg


def test_parse_case_arg_ok():
    car_id, expected = _parse_case_arg("41701817=monthly_finance")
    assert car_id == "41701817"
    assert expected == "monthly_finance"


def test_load_cases_dedup_cli_last_wins():
    cases = _load_cases("", ["1=sale", "1=monthly_finance"])
    assert len(cases) == 1
    assert cases[0]["car_id"] == "1"
    assert cases[0]["expected_intent"] == "monthly_finance"
