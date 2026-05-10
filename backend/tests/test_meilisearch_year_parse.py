from fastapi_app.meilisearch_query import _parse_year


def test_parse_year_plain():
    assert _parse_year("2018") == 2018


def test_parse_year_with_suffix_ru():
    assert _parse_year("2018 г.") == 2018
    assert _parse_year("год 2019") == 2019


def test_parse_year_yyyymm_numeric():
    assert _parse_year("202103") == 2021
