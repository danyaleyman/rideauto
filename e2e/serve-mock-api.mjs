/**
 * E2E mock API for Next smoke tests.
 * Serves /api/health, /api/search, /api/car/:id, /api/similar, /api/facets,
 * /api/catalog/daily-additions, POST /api/lead.
 */
import http from "node:http";

const PORT = 28765;

const CARS = [
  {
    id: "c1",
    title: "Hyundai Solaris 2020",
    price: 1650000,
    year_num: 2020,
    data: {
      mark: "Hyundai",
      model: "Solaris",
      year: "2020",
      km_age: 50000,
      engine_type: "Petrol",
      transmission_type: "AT",
      body_type: "Sedan",
      color: "White",
      drive_type: "FWD",
      images: ["https://picsum.photos/seed/c1/1200/800"],
      url: "https://example.com/c1",
    },
  },
  {
    id: "c2",
    title: "Hyundai Accent 2019",
    price: 1490000,
    year_num: 2019,
    data: {
      mark: "Hyundai",
      model: "Accent",
      year: "2019",
      km_age: 60000,
      engine_type: "Petrol",
      transmission_type: "AT",
      body_type: "Sedan",
      color: "Silver",
      drive_type: "FWD",
      images: ["https://picsum.photos/seed/c2/1200/800"],
    },
  },
];

function json(res, code, body) {
  const raw = JSON.stringify(body);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(raw),
  });
  res.end(raw);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);

  if (url.pathname === "/api/health") {
    return json(res, 200, { status: "ok", service: "mock-api" });
  }

  if (url.pathname === "/api/search" || url.pathname === "/api/cars") {
    return json(res, 200, {
      result: CARS,
      meta: {
        total: CARS.length,
        limit: 10,
        per_page: 10,
        pages: 1,
        offset: 0,
        next_cursor: null,
        next_page: null,
      },
    });
  }

  if (url.pathname === "/api/catalog/daily-additions") {
    const region = url.searchParams.get("region") || "korea";
    return json(res, 200, {
      count: 0,
      region,
      local_date: "2026-05-02",
      timezone: "Asia/Vladivostok",
    });
  }

  if (url.pathname === "/api/lead") {
    if (req.method !== "POST") return json(res, 404, { detail: "not found" });
    for await (const ch of req) ch; // drain body
    return json(res, 202, { status: "accepted" });
  }

  if (url.pathname.startsWith("/api/car/")) {
    const id = decodeURIComponent(url.pathname.slice("/api/car/".length));
    const car = CARS.find((x) => x.id === id);
    if (!car) return json(res, 404, { detail: "not found" });
    return json(res, 200, { result: car });
  }

  if (url.pathname === "/api/similar") {
    const carId = url.searchParams.get("car_id") || "";
    const limit = Number(url.searchParams.get("limit") || "8");
    const result = CARS.filter((x) => x.id !== carId).slice(0, Math.max(1, limit));
    return json(res, 200, {
      result,
      meta: { car_id: carId, limit: Math.max(1, limit), total_candidates: result.length },
    });
  }

  if (url.pathname === "/api/facets") {
    return json(res, 200, {
      marks: [{ value: "Hyundai", count: 2 }],
      models: [{ value: "Solaris", count: 1 }, { value: "Accent", count: 1 }],
      generations: [],
      trims: [],
      bodies: [{ value: "Sedan", count: 2 }],
      fuels: [{ value: "Petrol", count: 2 }],
      transmissions: [{ value: "AT", count: 2 }],
      colors: [{ value: "White", count: 1 }, { value: "Silver", count: 1 }],
    });
  }

  return json(res, 404, { detail: "not found" });
});

server.listen(PORT, "127.0.0.1", () => {
  // eslint-disable-next-line no-console
  console.log(`[mock-api] http://127.0.0.1:${PORT}`);
});

function shutdown() {
  server.close(() => process.exit(0));
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
