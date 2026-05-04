from scraper_pipeline.che168.taxonomy_sync import merge_che168_taxonomy_with_brand_api


def test_merge_brand_api_and_yaml_aliases():
    payload = {
        "result": {
            "list": [
                {"brandid": 15, "name": "BMW"},
                {"brandid": 99, "name": "奔驰", "englishname": "BenChi"},
            ]
        }
    }
    merged = merge_che168_taxonomy_with_brand_api(
        payload,
        {"mark_aliases": {"bmw": "YAML wins"}},
    )
    assert merged["brand_by_id"]["15"] == "BMW"
    assert merged["brand_by_id"]["99"] == "奔驰"
    assert merged["mark_aliases"]["bmw"] == "YAML wins"
    assert merged["mark_aliases"].get("benchi") == "奔驰"
    assert "che168_brand_api" in merged["taxonomy_source"]
