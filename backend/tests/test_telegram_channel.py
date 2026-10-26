"""Caption + scoring + Telegram send for the channel publisher."""
from __future__ import annotations

from unittest.mock import patch

from fastapi_app.config import Settings
from fastapi_app.encar_option_ru import sanitize_trim_name
from fastapi_app.rf_popular_models import is_rf_popular_listing
from fastapi_app.telegram_channel import (
    build_channel_caption,
    build_channel_html,
    caption_to_html,
    channel_telegram_configured,
    collect_equipment_labels,
    collect_photo_urls,
    has_turnkey_customs_price,
    is_petrol_or_diesel,
    score_channel_deal,
    send_channel_article_sync,
    source_to_market,
)


def test_source_to_market():
    assert source_to_market("encar") == "korea"
    assert source_to_market("che168") == "china"
    assert source_to_market("autotrader") == "usa"


def test_channel_configured_uses_lead_token_fallback():
    s = Settings(
        channel_telegram_bot_token="",
        channel_telegram_chat_id="@worldrideauto",
        lead_telegram_bot_token="tok",
    )
    assert channel_telegram_configured(s) is True
    assert channel_telegram_configured(Settings(channel_telegram_chat_id="")) is False


def test_build_channel_caption_matches_sample_blocks():
    text = build_channel_caption(
        title="Chevrolet (GM Daewoo) Trailblazer 1.3 Turbo 4WD RS",
        price_rub=2_140_000,
        market="korea",
        published_at="2026-07-23",
        data={
            "source": "encar",
            "engine_type": "бензин",
            "displacement_cc": 1300,
            "power_hp": 156,
            "power_kw": 115,
            "torque_nm": 236,
            "drive_type": "AWD",
            "transmission_type": "automatic",
            "year_month": 202307,
            "km_age": 36472,
            "trim_name": "RS",
            "che168_recommended_options": ["Смарт-ключ / бесключевой доступ", "Запуск двигателя кнопкой"],
        },
    )
    assert text.startswith("**🇰🇷 Корея**")
    assert "🏎 Chevrolet (GM Daewoo) Trailblazer" in text
    assert "• Двигатель: 1.3 л, бензин (турбированный)" in text
    assert "• Мощность: 156 л.с. (115 кВт)" in text
    assert "• Крутящий момент: 236 Н·м" in text
    assert "• Привод: полный — AWD (4WD)" in text
    assert "• Трансмиссия: автоматическая" in text
    assert "• Дата выпуска: 2023.07" in text
    assert "• Пробег: 36 472 км" in text
    assert "**Комплектация RS:**" in text
    assert "> Смарт-ключ / бесключевой доступ" in text
    assert "2 140 000 руб." in text
    assert "23.07.2026" in text
    assert "[⬇️ Оставить заявку](https://rideauto.ru/buy)" in text
    assert "[📞 Связаться](https://t.me/nikits15)" in text
    assert "**🇰🇷 Корея**\n\n**🏎 " in text
    assert "• Двигатель:" in text and "\n• Привод:" in text

    html_body = build_channel_html(
        title="Chevrolet (GM Daewoo) Trailblazer 1.3 Turbo 4WD RS",
        price_rub=2_140_000,
        market="korea",
        published_at="2026-07-23",
        data={
            "source": "encar",
            "engine_type": "бензин",
            "displacement_cc": 1300,
            "drive_type": "AWD",
            "trim_name": "RS",
            "che168_recommended_options": ["Смарт-ключ / бесключевой доступ"],
        },
    )
    assert html_body.startswith("<p><b>🇰🇷 Корея</b><br><br><b>🏎 ")
    assert "<b>Комплектация RS:</b>" in html_body
    assert "<b>💳 Цена во Владивостоке под ключ:" in html_body
    assert "<h2>" not in html_body and "<h3>" not in html_body
    assert "<br>• Привод:" in html_body
    assert "<blockquote>" in html_body and "&gt; Смарт-ключ" in html_body
    assert "</blockquote><p>\u00a0</p>" in html_body
    assert 'href="https://rideauto.ru/buy">⬇️ Оставить заявку</a>' in html_body
    converted = caption_to_html(text)
    assert converted.startswith("<p><b>🇰🇷 Корея</b>")
    assert "<b>Комплектация RS:</b>" in converted


def test_korea_photos_put_front_before_rear():
    urls = collect_photo_urls(
        {
            "source": "encar",
            "images": ["https://ci.encar.com/carpicture/rear_001.jpg"],
            "h_images": [
                {"path": "/rear_001.jpg", "type": "후면", "desc": "후면"},
                {"path": "/front_003.jpg", "type": "전면", "desc": "전면"},
            ],
        }
    )
    assert "front_003" in urls[0]
    assert any("rear_001" in u for u in urls)


def test_collect_photo_urls_dedupes_and_builds_encar_paths():
    urls = collect_photo_urls(
        {
            "images": [
                "https://ci.encar.com/carpicture/a.jpg",
                "https://ci.encar.com/carpicture/a.jpg?x=1",
            ],
            "h_images": [{"path": "/b.jpg"}],
        }
    )
    assert any("carpicture/a.jpg" in u for u in urls)
    assert any("/carpicture/b.jpg" in u for u in urls)


def test_encar_equipment_uses_official_codes_not_invented_names():
    labels = collect_equipment_labels(
        {
            "source": "encar",
            "options": {
                "standard": [
                    "001",
                    "014",
                    "022",
                    "024",
                    "057",
                    "068",
                    "079",
                    "096",
                ]
            },
        }
    )
    assert "ABS" in labels
    assert "Кожаные сиденья" in labels
    assert "Подогрев передних сидений" in labels
    assert "Электроскладывание зеркал" in labels
    assert "Смарт-ключ" in labels
    assert "Круиз-контроль" in labels
    assert "Адаптивный круиз-контроль" in labels
    assert "Bluetooth" in labels
    assert "Память положения сиденья пассажира" not in labels
    assert "Панорамная крыша / люк" not in labels


def test_equipment_rejects_hangul_and_sanitizes_trim():
    labels = collect_equipment_labels(
        {
            "source": "encar",
            "options": {"standard": ["001", "058"]},
            "extra": {
                "sellingpoint": {
                    "choiceOptionPhotos": [
                        {"partCode": "NAV", "partName": "8인치 스마트 내비게이션 + 조향연동 후방카메라"},
                        {"partCode": "SPEC_X", "partName": "should skip"},
                    ]
                }
            },
        }
    )
    assert "ABS" in labels
    assert "Камера заднего вида" in labels
    assert all("인치" not in x and not any("\uac00" <= ch <= "\ud7a3" for ch in x) for x in labels)
    caption = build_channel_caption(
        title="Hyundai LF Sonata 2.0",
        price_rub=1_900_000,
        market="korea",
        published_at="2026-10-26",
        data={"source": "encar", "trim_name": "2.0 케어플러스", "engine_type": "бензин"},
    )
    assert "케어플러스" not in caption
    assert "Комплектация 2.0:" in caption
    assert sanitize_trim_name("2.0 케어플러스") == "2.0"


def test_rf_popular_models_for_channel():
    assert is_rf_popular_listing({"mark": "Hyundai", "model": "Sonata"}) is True
    assert is_rf_popular_listing({"mark": "Kia", "model": "K5"}) is True
    assert is_rf_popular_listing({"mark": "Geely", "model": "Monjaro"}) is True
    assert is_rf_popular_listing({"mark": "Haval", "model": "Jolion"}) is True
    assert is_rf_popular_listing({"mark": "Hyundai", "model": "Nexo"}) is False
    assert is_rf_popular_listing({"mark": "Ferrari", "model": "Roma"}) is False


def test_autopost_fuel_and_turnkey_rules():
    assert is_petrol_or_diesel({"engine_type": "Бензин"}) is True
    assert is_petrol_or_diesel({"fuel_type": "디젤"}) is True
    assert is_petrol_or_diesel({"engine_type": "하이브리드"}) is False
    assert is_petrol_or_diesel({"engine_type": "가솔린+전기"}) is False
    assert is_petrol_or_diesel({"engine_type": "LPi"}) is False
    assert has_turnkey_customs_price({"pricing_tier": "full_customs"}, 2_000_000) is True
    assert has_turnkey_customs_price({"pricing_tier": "korea_land_only"}, 2_000_000) is False
    assert has_turnkey_customs_price({"pricing_tier": "full_customs"}, None) is False


def test_score_prefers_korea_fresh_low_mileage():
    good = score_channel_deal(
        source="encar",
        price_rub=2_100_000,
        mileage_km=30_000,
        year=2023,
        photo_count=8,
        damaged_parts=0,
    )
    weak = score_channel_deal(
        source="che168",
        price_rub=7_000_000,
        mileage_km=180_000,
        year=2018,
        photo_count=3,
        damaged_parts=4,
    )
    assert good > weak


def test_send_rich_message_ok():
    settings = Settings(
        channel_telegram_bot_token="tok",
        channel_telegram_chat_id="@worldrideauto",
    )
    with patch("fastapi_app.telegram_channel._tg_json") as m:
        m.return_value = {"ok": True, "result": {"message_id": 7}}
        out = send_channel_article_sync(
            photo_urls=["https://rideauto.ru/api/images/a?size=medium"],
            text="🇰🇷 Корея",
            settings=settings,
        )
        assert out == {"ok": True, "mode": "rich", "message_id": 7}
        assert m.call_args[0][1] == "sendRichMessage"
        rich = m.call_args[0][2]["rich_message"]
        assert "blocks" not in rich
        assert "html" in rich
        assert "<tg-slideshow>" in rich["html"] or "<img src=" in rich["html"]
        assert "🇰🇷 Корея" in rich["html"]


def test_send_falls_back_to_album():
    settings = Settings(
        channel_telegram_bot_token="tok",
        channel_telegram_chat_id="@worldrideauto",
    )

    def _fake(token, method, payload, timeout=45):  # noqa: ARG001
        if method == "sendRichMessage":
            raise RuntimeError("telegram_http_404")
        return {"ok": True, "result": [{"message_id": 11}]}

    with patch("fastapi_app.telegram_channel._tg_json", side_effect=_fake):
        out = send_channel_article_sync(
            photo_urls=["https://rideauto.ru/api/images/a?size=medium"],
            text="short",
            settings=settings,
        )
    assert out["ok"] is True
    assert out["mode"] == "album"
