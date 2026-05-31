from localization.term_localizer import facet_canonical_english


def test_facet_canonical_korean_bmw_series():
    assert facet_canonical_english("1시리즈", "model") == "1 Series"
    assert facet_canonical_english("2시리즈", "model") == "2 Series"
    assert facet_canonical_english("4시리즈", "model") == "4 Series"
    assert facet_canonical_english("6시리즈", "model") == "6 Series"
    assert facet_canonical_english("3시리즈", "model") == "3 Series"
    assert facet_canonical_english("5시리즈", "model") == "5 Series"


def test_facet_canonical_repairs_romanized_series_garbage():
    assert facet_canonical_english("1silijeu", "model") == "1 Series"
    assert facet_canonical_english("2silijeu", "model") == "2 Series"
    assert facet_canonical_english("6silijeu", "model") == "6 Series"


def test_facet_canonical_encar_hyphen_series():
    assert facet_canonical_english("1-Series", "model") == "1 Series"
