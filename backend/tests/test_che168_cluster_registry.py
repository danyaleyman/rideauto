from scraper_pipeline.che168.cluster_registry import (
    apply_che168_cluster_registry,
    che168_cluster_keys_from_listing_data,
)


def test_cluster_keys_from_listing():
    d = {
        "source": "che168",
        "che168_listing_cluster_id": "che168:attr:ab",
        "vin": " WBAZZZ12345678901 ",
    }
    keys = che168_cluster_keys_from_listing_data(d)
    assert "che168:attr:ab" in keys
    assert any(k.startswith("vin:") and "WBAZZZ12345678901" in k for k in keys)


class _Cur:
    def __init__(self) -> None:
        self.keys: dict[str, list[str]] = {}
        self.dedupe_updates: list[tuple] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        sql_u = " ".join(sql.split())
        if "INSERT INTO che168_cluster_registry" in sql_u:
            k, cid = params[0], params[1]
            self.keys.setdefault(k, []).append(cid)
        elif sql_u.startswith("SELECT car_id FROM che168_cluster_registry"):
            k = params[0]
            self._rows = [(x,) for x in self.keys.get(k, [])]
        elif "dedupe_canonical_car_id = NULL" in sql_u:
            self.dedupe_updates.append(("clear", params[0]))
        elif "dedupe_canonical_car_id = %s" in sql_u and "NULL" not in sql_u:
            self.dedupe_updates.append(("set", params[0], params[1]))

    def fetchall(self):
        return self._rows


def test_apply_registry_marks_duplicate():
    cur = _Cur()
    cur.keys["ck"] = ["che168-200", "che168-100"]
    data = {"source": "che168", "che168_listing_cluster_id": "ck"}
    apply_che168_cluster_registry(cur, "che168-200", data)
    assert ("clear", "che168-100") in cur.dedupe_updates
    assert ("set", "che168-100", "che168-200") in cur.dedupe_updates
