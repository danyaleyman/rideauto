from __future__ import annotations

from encar_listing_status import encar_detail_indicates_sold, encar_listing_gone_from_api


def test_http_404_means_gone() -> None:
    assert encar_listing_gone_from_api(404, {}) is True


def test_http_200_empty_not_sold() -> None:
    assert encar_listing_gone_from_api(200, {}) is False


def test_sales_status_sold() -> None:
    assert encar_detail_indicates_sold({"salesStatus": "SOLD"}) is True


def test_advertisement_sales_status_korean() -> None:
    assert encar_detail_indicates_sold({"advertisement": {"salesStatus": "판매완료"}}) is True


def test_active_like_missing_status() -> None:
    assert encar_detail_indicates_sold({"advertisement": {"advertisementType": "NORMAL"}}) is False
