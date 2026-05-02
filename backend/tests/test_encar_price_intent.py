from encar_price_intent import classify_encar_price_intent


def test_classify_reserved_placeholder_digits():
    intent, signals = classify_encar_price_intent({"source": "encar", "price": "4444"})
    assert intent == "reserved_placeholder"
    assert "reserved_placeholder_digits" in signals


def test_classify_monthly_finance_from_price_text():
    intent, signals = classify_encar_price_intent(
        {
            "source": "encar",
            "price": "432",
            "price_text": "월36만원 월렌트(12개월) 인수금 0만원",
        }
    )
    assert intent == "monthly_finance"
    assert "monthly_amount" in signals


def test_classify_regular_sale():
    intent, signals = classify_encar_price_intent(
        {"source": "encar", "price_won": 450900000, "price": "45090", "price_text": "엔카금융 안내"}
    )
    assert intent == "sale"
    assert signals == []


def test_strong_list_price_overrides_weak_finance_boilerplate():
    """Типичный Encar: большая цена + общий текст про 할부/개월 без явного 월N만원."""
    intent, signals = classify_encar_price_intent(
        {
            "source": "encar",
            "price_won": 13_900_000,
            "price": "1390",
            "year": "2018",
            "km_age": "141452",
            "price_text": "무이자 할부 36개월 프로모션 문의",
        }
    )
    assert intent == "sale"
    assert "sale_price_overrides_weak_finance_text" in signals

