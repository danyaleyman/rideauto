from scraper_pipeline.che168.api_outcome import (
    che168_carinfo_outcome,
    che168_extract_similar_ids,
    che168_response_suggests_session_refresh,
    che168_search_pagecount,
)


def test_response_suggests_session_refresh():
    assert che168_response_suggests_session_refresh({}) is False
    assert che168_response_suggests_session_refresh({"returncode": 0}) is False
    assert (
        che168_response_suggests_session_refresh({"returncode": 1, "message": "please login first"}) is True
    )


def test_carinfo_gone_http():
    assert che168_carinfo_outcome(404, {}) == "gone"
    assert che168_carinfo_outcome(410, {}) == "gone"


def test_carinfo_retry_non_200():
    assert che168_carinfo_outcome(503, None) == "retry"
    assert che168_carinfo_outcome(500, {"a": 1}) == "retry"


def test_carinfo_gone_business_code():
    assert che168_carinfo_outcome(200, {"returncode": 100, "message": "listing off"}) == "gone"


def test_carinfo_retry_session():
    assert che168_carinfo_outcome(200, {"returncode": 1, "message": "please login session"}) == "retry"


def test_carinfo_ok_minimal_body():
    assert che168_carinfo_outcome(200, {"result": {"id": 1, "title": "x", "price": 100}}) == "ok"


def test_search_pagecount():
    assert che168_search_pagecount({"pagecount": 12}) == 12
    assert che168_search_pagecount({"pageCount": "5"}) == 5


def test_similar_ids():
    assert che168_extract_similar_ids({"result": {"list": [{"id": 1}, {"infoId": "2"}]}}) == ["1", "2"]
