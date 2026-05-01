from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from parser_full import EncarFullParser

JSON_SCALAR = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10_000, max_value=10_000),
    st.floats(allow_nan=False, allow_infinity=False, width=16),
    st.text(max_size=40),
)

JSON_LIKE = st.recursive(
    JSON_SCALAR,
    lambda children: st.one_of(
        st.lists(children, max_size=6),
        st.dictionaries(
            st.sampled_from(
                [
                    "master",
                    "detail",
                    "inners",
                    "outers",
                    "items",
                    "type",
                    "statusType",
                    "children",
                    "title",
                    "name",
                    "result",
                    "resultCode",
                    "partName",
                ]
            ),
            children,
            max_size=8,
        ),
    ),
    max_leaves=40,
)


@settings(max_examples=250, deadline=None)
@given(inspection=JSON_LIKE, diagnosis=JSON_LIKE)
def test_parse_inspection_property_never_crashes_and_keeps_contract(inspection, diagnosis) -> None:
    parser = EncarFullParser()
    result = parser.parse_inspection(inspection, diagnosis)
    expected_keys = {
        "basicInfo",
        "engineTransmission",
        "chassis",
        "electrical",
        "interior",
        "bodyChanged",
        "additional",
        "bodyPanels",
        "bodyComments",
    }
    assert isinstance(result, dict)
    assert expected_keys.issubset(set(result.keys()))
    assert isinstance(result["bodyPanels"], list)
    assert isinstance(result["bodyChanged"], dict)
    assert isinstance(result["bodyComments"], str)
