from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from parser_full import EncarFullParser


SCALAR = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-100_000, max_value=100_000),
    st.floats(allow_nan=False, allow_infinity=False, width=16),
    st.text(max_size=40),
)

SMALL_DICT = st.dictionaries(
    st.text(min_size=1, max_size=20),
    SCALAR,
    max_size=6,
)

DETAIL = st.fixed_dictionaries(
    {
        "vin": SCALAR,
        "vehicleNo": SCALAR,
        "spec": st.one_of(
            SMALL_DICT,
            st.fixed_dictionaries({"fuelName": SCALAR, "driveType": SCALAR, "seatCount": SCALAR}),
            st.fixed_dictionaries({"engineDisplacement": SCALAR, "transmissionName": SCALAR}),
            st.lists(SCALAR, max_size=4),
        ),
        "category": st.one_of(SMALL_DICT, st.fixed_dictionaries({"manufacturerName": SCALAR, "modelName": SCALAR})),
        "contact": st.one_of(SMALL_DICT, st.fixed_dictionaries({"userType": SCALAR, "no": SCALAR, "address": SCALAR})),
        "manage": st.one_of(SMALL_DICT, st.fixed_dictionaries({"firstAdvertisedDateTime": SCALAR})),
        "advertisement": st.one_of(SMALL_DICT, st.fixed_dictionaries({"salesStatus": SCALAR})),
        "condition": st.one_of(SMALL_DICT, st.fixed_dictionaries({"inspection": st.fixed_dictionaries({"formats": st.one_of(st.lists(SCALAR, max_size=4), SCALAR)})})),
        "options": st.one_of(SMALL_DICT, st.fixed_dictionaries({"standard": st.one_of(st.lists(SCALAR, max_size=4), SCALAR)})),
        "photos": st.one_of(
            st.lists(st.fixed_dictionaries({"path": st.text(max_size=20), "type": SCALAR}), max_size=4),
            SCALAR,
        ),
    }
)

ITEM = st.fixed_dictionaries(
    {
        "Manufacturer": SCALAR,
        "Model": SCALAR,
        "Badge": SCALAR,
        "Year": SCALAR,
        "Month": SCALAR,
        "Price": SCALAR,
        "Mileage": SCALAR,
        "Description": SCALAR,
        "Separation": st.one_of(st.lists(st.text(max_size=10), max_size=3), SCALAR),
    }
)


@settings(max_examples=80, deadline=None)
@given(
    item=ITEM,
    detail=DETAIL,
    diagnosis=st.one_of(
        st.dictionaries(st.text(min_size=1, max_size=16), SCALAR, max_size=4),
        st.fixed_dictionaries({"items": st.lists(st.fixed_dictionaries({"name": st.text(max_size=20), "resultCode": st.text(max_size=20)}), max_size=4)}),
    ),
    inspection=st.one_of(
        st.dictionaries(st.text(min_size=1, max_size=16), SCALAR, max_size=4),
        st.fixed_dictionaries({"master": st.fixed_dictionaries({"detail": st.dictionaries(st.text(max_size=20), SCALAR, max_size=6)}), "inners": st.lists(SCALAR, max_size=4), "outers": st.lists(SCALAR, max_size=4)}),
    ),
    sellingpoint=st.dictionaries(st.text(min_size=1, max_size=16), SCALAR, max_size=4),
    record=st.one_of(
        st.dictionaries(st.text(min_size=1, max_size=16), SCALAR, max_size=4),
        st.fixed_dictionaries({"insuranceCases": SCALAR}),
        st.fixed_dictionaries({"claimAmount": SCALAR}),
    ),
    user_info=st.one_of(st.none(), st.dictionaries(st.text(min_size=1, max_size=16), SCALAR, max_size=4), st.fixed_dictionaries({"userId": st.text(max_size=20)})),
    inspection_structured=st.one_of(
        st.dictionaries(st.text(min_size=1, max_size=16), SCALAR, max_size=4),
        st.fixed_dictionaries({"bodyChanged": st.dictionaries(st.text(max_size=20), st.text(max_size=20), max_size=6)}),
    ),
)
def test_normalize_car_property_keeps_contract_and_no_crash(
    item,
    detail,
    diagnosis,
    inspection,
    sellingpoint,
    record,
    user_info,
    inspection_structured,
) -> None:
    parser = EncarFullParser()
    photos = detail.get("photos", []) if isinstance(detail, dict) and isinstance(detail.get("photos"), list) else []
    out = parser.normalize_car(
        car_id="100001",
        item=item,
        detail=detail,
        photos=photos,
        diagnosis=diagnosis if isinstance(diagnosis, dict) else {},
        inspection=inspection if isinstance(inspection, dict) else {},
        sellingpoint=sellingpoint if isinstance(sellingpoint, dict) else {},
        record=record if isinstance(record, dict) else {},
        user_info=user_info if isinstance(user_info, dict) else None,
        inspection_structured=inspection_structured if isinstance(inspection_structured, dict) else {},
    )
    data = out["data"]
    assert data["parser_schema_version"] == "encar.v2"
    assert isinstance(data["data_quality"], dict)
    assert "reasons" in data["data_quality"]
    assert isinstance(data["price_won"], int)
