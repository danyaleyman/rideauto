/**
 * k6 smoke/load для публичного поиска каталога.
 *
 *   k6 run deploy/k6/catalog-search.js -e BASE_URL=https://rideauto.ru -e VUS=10 -e DURATION=30s
 */
import http from "k6/http";
import { check, sleep } from "k6";

const base = (__ENV.BASE_URL || "http://127.0.0.1:8080").replace(/\/+$/, "");

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || "20s",
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<800"],
  },
};

export default function () {
  const urls = [
    `${base}/api/search?region=korea&source=encar&per_page=24`,
    `${base}/api/search?region=china&source=che168&per_page=24`,
    `${base}/api/facets?region=korea&source=encar`,
  ];
  const url = urls[Math.floor(Math.random() * urls.length)];
  const res = http.get(url, { headers: { Accept: "application/json" } });
  check(res, {
    "status 200": (r) => r.status === 200,
    "has result": (r) => {
      try {
        const j = r.json();
        return j && typeof j === "object";
      } catch {
        return false;
      }
    },
  });
  sleep(0.3);
}
