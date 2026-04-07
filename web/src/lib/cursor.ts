/** Совместимо с ``fastapi_app.cursor.encode_offset_cursor`` (base64url JSON). */

export function encodeOffsetCursor(offset: number, limit: number): string {
  const obj = { l: Math.max(1, Math.floor(limit)), o: Math.max(0, Math.floor(offset)), v: 1 };
  const json = JSON.stringify(obj);
  const bytes = new TextEncoder().encode(json);
  let bin = "";
  bytes.forEach((b) => {
    bin += String.fromCharCode(b);
  });
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

export function decodeOffsetCursor(token: string): { offset: number; limit: number } | null {
  const t = token.trim();
  if (!t) return null;
  const pad = "=".repeat((4 - (t.length % 4)) % 4);
  try {
    const bin = atob(t.replace(/-/g, "+").replace(/_/g, "/") + pad);
    const json = JSON.parse(bin) as { v?: number; o?: number; l?: number };
    if (json?.v !== 1 || typeof json.o !== "number" || typeof json.l !== "number") return null;
    if (json.o < 0 || json.l < 1) return null;
    return { offset: json.o, limit: json.l };
  } catch {
    return null;
  }
}
