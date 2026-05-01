from __future__ import annotations

import logging

import pytest

from parser_full import EncarFullParser
from scraper_pipeline.encar.client import AsyncEncarClient
from scraper_pipeline.encar.parser import parse_one_car_sync


def test_normalize_car_sets_contract_and_damage_summary() -> None:
    parser = EncarFullParser()
    item = {
        "Manufacturer": "BMW",
        "Model": "X5",
        "Badge": "xDrive40i",
        "Year": 2022,
        "Month": 6,
        "Price": 88000000,
        "Mileage": 12000,
        "Id": "123",
    }
    detail = {
        "vin": "VIN123",
        "vehicleNo": "12가1234",
        "spec": {"fuelName": "가솔린", "driveType": "4WD"},
        "category": {},
        "contact": {"userType": "DEALER", "no": "S1"},
        "manage": {},
        "advertisement": {},
        "condition": {"inspection": {"formats": []}},
        "photos": [],
        "options": {"standard": []},
    }
    diagnosis = {
        "items": [
            {"name": "HOOD", "resultCode": "REPLACEMENT"},
            {"name": "TRUNK_LID", "resultCode": "NORMAL"},
        ]
    }
    record = {
        "insuranceCases": 2,
        "nested": {"claimAmount": "1,250,000"},
    }
    inspection_structured = {"bodyChanged": {"Капот": "замена", "Левая дверь": "ремонт"}}

    normalized = parser.normalize_car(
        car_id="123",
        item=item,
        detail=detail,
        photos=[],
        diagnosis=diagnosis,
        inspection={},
        sellingpoint={},
        record=record,
        user_info={},
        inspection_structured=inspection_structured,
    )
    data = normalized["data"]
    assert data["parser_schema_version"] == "encar.v2"
    assert data["insurance_cases"] == 2
    assert data["insurance_payout_krw"] == 1250000
    assert data["damaged_parts_count"] == 2
    assert data["data_quality"]["detail_present"] is True
    assert data["data_quality"]["missing_required_fields"] == []
    assert "user_missing" in data["data_quality"]["reasons"]
    assert data["source"] == "encar"
    assert data["clean_schema_version"] == "encar.clean.v1"
    assert data["identity_clean"]["model"] == "X5"
    assert data["pricing_clean"]["price_intent"] in {"sale", "monthly_finance", "reserved_placeholder", "unknown"}
    assert "Manufacturer" in data["parser_source_shapes"]["list_item"]
    assert data["parser_source_shapes_hash"]["list_item"]


def test_parse_one_car_sync_logs_exception(caplog: pytest.LogCaptureFixture) -> None:
    class BrokenParser:
        def parse_inspection(self, *_args, **_kwargs):
            raise RuntimeError("boom")

        def normalize_car(self, *_args, **_kwargs):
            return {}

    caplog.set_level(logging.ERROR)
    out = parse_one_car_sync(
        parser=BrokenParser(),  # type: ignore[arg-type]
        car_id="1",
        item={},
        detail={},
        diagnosis={},
        record={},
        inspection={},
        sellingpoint={},
        user_info={},
    )
    assert out is None
    assert "normalize failed for car_id=1" in caplog.text


@pytest.mark.asyncio
async def test_fetch_record_passes_plain_vehicle_no() -> None:
    cfg = {
        "http": {},
        "retry": {"max_attempts": 1, "retry_statuses": []},
        "proxy": {"enabled": False, "urls": []},
        "user_agents": ["ua"],
    }
    client = AsyncEncarClient(cfg, logging.getLogger("test"))
    captured = {}

    async def fake_request(_method, _url, headers=None, params=None, origin=""):
        captured["params"] = params
        return {"ok": True}, 200, None

    client._request = fake_request  # type: ignore[method-assign]
    data, status, err = await client.fetch_record("123", "12가1234")
    assert status == 200 and err is None and data == {"ok": True}
    assert captured["params"] == {"vehicleNo": "12가1234"}


def test_normalize_car_handles_malformed_record_numbers() -> None:
    parser = EncarFullParser()
    item = {"Manufacturer": "Kia", "Model": "K5", "Year": 2020, "Id": "777"}
    detail = {"spec": {}, "category": {}, "contact": {}, "manage": {}, "advertisement": {}, "options": {}}
    bad_record = {
        "insuranceCases": "N/A",
        "claimAmount": "KRW unknown",
    }
    normalized = parser.normalize_car(
        car_id="777",
        item=item,
        detail=detail,
        photos=[],
        diagnosis={},
        inspection={},
        sellingpoint={},
        record=bad_record,
        user_info=None,
        inspection_structured={},
    )
    data = normalized["data"]
    assert data["insurance_cases"] == 0
    assert data["insurance_payout_krw"] == 0


def test_parse_one_car_sync_attaches_raw_envelope_and_integrity() -> None:
    parser = EncarFullParser()
    out = parse_one_car_sync(
        parser=parser,
        car_id="9001",
        item={"Manufacturer": "BMW", "Model": "X3", "Year": 2021, "Id": "9001"},
        detail={"spec": {}, "category": {}, "contact": {}, "manage": {}, "advertisement": {}, "options": {}},
        diagnosis={},
        record={},
        inspection={},
        sellingpoint={},
        user_info={},
        source_meta={"detail": {"status": 200, "ok": True, "latency_ms": 120}},
    )
    assert out is not None
    data = out["data"]
    assert "raw_envelope" in data
    envelope = data["raw_envelope"]
    assert envelope["raw_schema_version"] == "encar.raw.v1"
    assert "integrity" in envelope
    assert envelope["source_meta"]["detail"]["status"] == 200
    assert isinstance(envelope["integrity"]["missing_sources"], list)
    assert "_raw" in out
    assert isinstance(data["data_quality"]["raw_quality_score"], int)
