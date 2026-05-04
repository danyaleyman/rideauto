from parser_audit_common import audit_pct


def test_audit_pct():
    assert audit_pct(1, 4) == 25.0
    assert audit_pct(0, 0) == 0.0
