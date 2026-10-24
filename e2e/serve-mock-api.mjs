/**
 * E2E mock API for Next smoke / catalog UI tests.
 * Serves /api/health, /api/search, /api/car/:id, /api/similar, /api/facets,
 * /api/catalog/daily-additions, POST /api/lead, /api/compare.
 */
import http from "node:http";

const PORT = 28765;

const CARS = [
  {
    id: "c1",
    title: "Hyundai Solaris 2020",
    price: 1650000,
    year_num: 2020,
    region: "korea",
    data: {
      mark: "Hyundai",
      model: "Solaris",
      cluster: "Solaris",
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
    region: "korea",
    data: {
      mark: "Hyundai",
      model: "Accent",
      cluster: "Accent",
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
  {
    id: "c3",
    title: "Kia Rio 2021",
    price: 1390000,
    year_num: 2021,
    region: "korea",
    data: {
      mark: "Kia",
      model: "Rio",
      cluster: "Rio",
      year: "2021",
      km_age: 32000,
      engine_type: "Petrol",
      transmission_type: "MT",
      body_type: "Sedan",
      color: "Black",
      drive_type: "FWD",
      images: ["https://picsum.photos/seed/c3/1200/800"],
    },
  },
  {
    id: "c4",
    title: "BYD Seal 2023",
    price: 3200000,
    year_num: 2023,
    region: "china",
    data: {
      mark: "BYD",
      model: "Seal",
      cluster: "Seal",
      year: "2023",
      km_age: 12000,
      engine_type: "Electric",
      transmission_type: "AT",
      body_type: "Sedan",
      color: "Blue",
      drive_type: "RWD",
      source: "che168",
      images: ["https://picsum.photos/seed/c4/1200/800"],
    },
  },
  {
    id: "autotrader-1001",
    title: "Toyota Camry 2021",
    price: 2450000,
    year_num: 2021,
    region: "usa",
    pricing_tier: "full_customs",
    catalog_created_at: new Date().toISOString(),
    data: {
      mark: "Toyota",
      model: "Camry",
      cluster: "Camry",
      year: "2021",
      km_age: 28000,
      engine_type: "Petrol",
      transmission_type: "AT",
      body_type: "Sedan",
      color: "White",
      drive_type: "FWD",
      source: "autotrader",
      power_hp: 203,
      images: ["https://picsum.photos/seed/usa1/1200/800"],
    },
  },
];

function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization");
}

function json(res, code, body) {
  const raw = JSON.stringify(body);
  cors(res);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(raw),
  });
  res.end(raw);
}

function splitCsv(sp, key) {
  return (sp.get(key) || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function regionOf(car) {
  return String(car.region || "korea").toLowerCase();
}

function resolveRegion(sp) {
  const raw = (sp.get("region") || "").toLowerCase();
  if (raw === "china" || raw === "usa" || raw === "korea") return raw;
  return "korea";
}

function filterCars(sp) {
  const region = resolveRegion(sp);
  const marks = splitCsv(sp, "marks");
  const models = splitCsv(sp, "models");
  const q = (sp.get("q") || "").trim().toLowerCase();
  return CARS.filter((car) => {
    if (regionOf(car) !== region) return false;
    if (marks.length && !marks.includes(car.data.mark)) return false;
    if (models.length && !models.includes(car.data.model)) return false;
    if (q) {
      const hay = `${car.title} ${car.data.mark} ${car.data.model}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function countBy(cars, pick) {
  const map = new Map();
  for (const car of cars) {
    const value = pick(car);
    if (!value) continue;
    map.set(value, (map.get(value) || 0) + 1);
  }
  return [...map.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, label: value, count, values: [value] }));
}

function buildFacets(sp) {
  const region = resolveRegion(sp);
  const inRegion = CARS.filter((c) => regionOf(c) === region);
  const marks = splitCsv(sp, "marks");
  const modelsPool = marks.length
    ? inRegion.filter((c) => marks.includes(c.data.mark))
    : inRegion;
  return {
    marks: countBy(inRegion, (c) => c.data.mark),
    clusters: countBy(modelsPool, (c) => c.data.cluster || c.data.model),
    models: countBy(modelsPool, (c) => c.data.model),
    generations: [],
    trims: [],
    bodies: countBy(modelsPool, (c) => c.data.body_type),
    fuels: countBy(modelsPool, (c) => c.data.engine_type),
    transmissions: countBy(modelsPool, (c) => c.data.transmission_type),
    colors: countBy(modelsPool, (c) => c.data.color),
  };
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);

  // Browser calls mock from Next :24173 (NEXT_PUBLIC_API_BASE) — need CORS.
  if (req.method === "OPTIONS") {
    cors(res);
    res.writeHead(204);
    res.end();
    return;
  }

  if (url.pathname === "/api/health") {
    return json(res, 200, { status: "ok", service: "mock-api" });
  }

  if (url.pathname === "/api/search" || url.pathname === "/api/cars") {
    const result = filterCars(url.searchParams);
    return json(res, 200, {
      result,
      meta: {
        total: result.length,
        limit: 10,
        per_page: 10,
        pages: Math.max(1, Math.ceil(result.length / 10) || 1),
        offset: 0,
        next_cursor: null,
        next_page: null,
      },
    });
  }

  if (url.pathname === "/api/catalog/daily-additions") {
    const region = resolveRegion(url.searchParams);
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
    const seed = CARS.find((x) => x.id === carId);
    const region = seed ? regionOf(seed) : "korea";
    const result = CARS.filter((x) => x.id !== carId && regionOf(x) === region).slice(
      0,
      Math.max(1, limit),
    );
    return json(res, 200, {
      result,
      meta: { car_id: carId, limit: Math.max(1, limit), total_candidates: result.length },
    });
  }

  if (url.pathname === "/api/facets") {
    return json(res, 200, buildFacets(url.searchParams));
  }

  if (url.pathname === "/api/compare") {
    const ids = (url.searchParams.get("ids") || "")
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean);
    const result = ids
      .map((id) => {
        const car = CARS.find((x) => x.id === id);
        if (!car) return null;
        return {
          id: car.id,
          title: car.title,
          mark: car.data.mark,
          model: car.data.model,
          year: car.data.year,
          mileage_km: car.data.km_age,
          price_rub: car.price,
          fuel: car.data.engine_type,
          transmission: car.data.transmission_type,
          body_type: car.data.body_type,
          drive_type: car.data.drive_type,
          thumb_url: car.data.images?.[0] ?? null,
          url_path: `/car/${car.id}`,
        };
      })
      .filter(Boolean);
    return json(res, 200, { result });
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
