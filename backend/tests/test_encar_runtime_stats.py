from scraper_pipeline.encar.runtime_stats import EncarStats


def test_encar_runtime_stats_snapshot() -> None:
    st = EncarStats(enabled=True)
    st.mark_parsed_ok()
    st.mark_with_images(fallback=False)
    st.mark_with_images(fallback=True)
    st.mark_with_user_info()
    snap = st.snapshot()
    assert snap["cars_parsed_ok"] == 1
    assert snap["cars_with_images"] == 2
    assert snap["cars_with_images_fallback"] == 1
    assert snap["cars_with_user_info"] == 1
