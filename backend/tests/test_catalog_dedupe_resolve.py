from catalog_dedupe import terminal_car_id_for_dedupe_map


def test_terminal_follows_chain():
    m = {"a": "b", "b": "c", "c": None}
    assert terminal_car_id_for_dedupe_map(m, "a") == "c"


def test_terminal_breaks_cycle():
    m = {"a": "b", "b": "a"}
    assert terminal_car_id_for_dedupe_map(m, "a") == "a"


def test_terminal_missing_key():
    m = {"x": None}
    assert terminal_car_id_for_dedupe_map(m, "unknown") == "unknown"
