import { describe, expect, it } from "vitest";
import { getAllCarPhotoUrls } from "./car-gallery-images";
import { normalizeEncarPhotoUrl } from "./car-images";

const FRONT = "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_001.jpg";
const REAR = "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_009.jpg";
const SIDE = "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_003.jpg";
const FULL = (url: string) => `${url}?impolicy=widthRate&rw=1920`;

describe("china gallery keeps autoimg photos and drops activity URLs", () => {
  it("does not collapse gallery to honestVehicleInspection / activity links", () => {
    const urls = getAllCarPhotoUrls({
      source: "che168",
      id: "che168-60322525",
      inner_id: "60322525",
      images: [
        "https://activitym.che168.com/2025/honestVehicleInspectionReport/main/index?infoid=x",
        "https://erscglobal2.autoimg.cn/escimg/auto/g34/M08/47/4C/1400x0_c42_autohomecar__Aaa.jpg.webp",
        "https://erscglobal2.autoimg.cn/escimg/auto/g34/M08/47/4C/1400x0_c42_autohomecar__Aaa.jpg.webp?format=webp&amp;w=360",
        "https://erscglobal2.autoimg.cn/escimg/auto/g33/M06/AA/75/640x480_c42_autohomecar__Bbb.jpg.webp",
      ],
    });
    expect(urls.some((u) => u.includes("activitym.che168"))).toBe(false);
    expect(urls.some((u) => u.includes("autohomecar__Aaa"))).toBe(true);
    expect(urls.filter((u) => u.includes("autohomecar__Aaa"))).toHaveLength(1);
    expect(urls.some((u) => u.includes("autohomecar__Bbb"))).toBe(false);
    expect(urls[0]).toContain("1400x0");
  });

  it("keeps a gallery that is only 640 thumbs", () => {
    const urls = getAllCarPhotoUrls({
      source: "che168",
      id: "che168-1",
      images: [
        "https://erscglobal2.autoimg.cn/escimg/auto/g1/640x480_c42_autohomecar__Aaa.jpg.webp",
        "https://erscglobal2.autoimg.cn/escimg/auto/g1/640x480_c42_autohomecar__Bbb.jpg.webp",
      ],
    });
    expect(urls).toHaveLength(2);
  });
});

describe("korea gallery uses full-size Encar photos without watermark crop", () => {
  it("normalizes bare encar jpg to widthRate (not the 640px default)", () => {
    expect(normalizeEncarPhotoUrl(FRONT)).toBe(FULL(FRONT));
  });

  it("strips stored wtmk/heightRate crop and upgrades to full frame", () => {
    const urls = getAllCarPhotoUrls({
      source: "encar",
      images: [
        "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_001.jpg?impolicy=heightRate&rh=696&cw=1160&ch=696&cg=Center&wtmk=https://ci.encar.com/wt_mark/w_mark_04.png",
        "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_009.jpg?impolicy=heightRate&wtmk=https://ci.encar.com/wt_mark/w_mark_04.png",
      ],
      h_images: [
        { path: "/carpicture08/pic4278/42789943_001.jpg", type: "EXT", desc: "전면" },
        { path: "/carpicture08/pic4278/42789943_009.jpg", type: "EXT", desc: "후면" },
      ],
    });
    expect(urls[0]).toBe(FULL(FRONT));
    expect(urls.some((u) => /wtmk=|heightRate|rh=696/i.test(u))).toBe(false);
    expect(urls.every((u) => u.includes("impolicy=widthRate"))).toBe(true);
  });

  it("keeps images[] order by face and does not prepend h_images", () => {
    const urls = getAllCarPhotoUrls({
      source: "encar",
      images: [REAR, SIDE, FRONT],
      h_images: [
        { path: "/carpicture08/pic4278/42789943_001.jpg", type: "EXT", desc: "전면" },
        { path: "/carpicture08/pic4278/42789943_003.jpg", type: "EXT", desc: "측면" },
        { path: "/carpicture08/pic4278/42789943_009.jpg", type: "EXT", desc: "후면" },
      ],
    });
    expect(urls.slice(0, 3)).toEqual([FULL(FRONT), FULL(SIDE), FULL(REAR)]);
  });

  it("puts front 3/4 before rear 3/4 even when rear has lower frame number", () => {
    const rearQ = "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_001.jpg";
    const frontQ = "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_009.jpg";
    const urls = getAllCarPhotoUrls({
      source: "encar",
      images: [rearQ, frontQ],
      h_images: [
        { path: "/carpicture08/pic4278/42789943_001.jpg", type: "EXT", desc: "후측면" },
        { path: "/carpicture08/pic4278/42789943_009.jpg", type: "EXT", desc: "전측면" },
      ],
    });
    expect(urls[0]).toBe(FULL(frontQ));
    expect(urls[1]).toBe(FULL(rearQ));
  });

  it("falls back to h_images as full-size URLs when images[] is empty", () => {
    const urls = getAllCarPhotoUrls({
      source: "encar",
      h_images: [{ path: "/carpicture08/pic4278/42789943_001.jpg", type: "EXT", desc: "전면" }],
    });
    expect(urls[0]).toBe(FULL(FRONT));
    expect(urls[0]).not.toContain("wtmk=");
  });

  it("uses URL seq-heuristic when h_images hints do not cover all images[] URLs", () => {
    // Encar listing: h_images only has ONE entry (the rear shot),
    // but images[] also has a front shot that is NOT mentioned in h_images.
    // Without the URL heuristic, the unmatched front shot gets rank=4 (unknown)
    // which is worse than rear rank=3 → rear ends up first. With the fix the
    // unmatched front (_001) gets rank=1 (seq ≤ 2 heuristic) → front comes first.
    const frontUnknown = "https://ci.encar.com/carpicture/carpicture08/pic9999/99999999_001.jpg";
    const rearKnown = "https://ci.encar.com/carpicture/carpicture08/pic9999/99999999_005.jpg";
    const urls = getAllCarPhotoUrls({
      source: "encar",
      images: [rearKnown, frontUnknown],
      h_images: [
        // Only the rear shot is described in h_images; front is absent.
        { path: "/carpicture08/pic9999/99999999_005.jpg", type: "EXT", desc: "후측면" },
      ],
    });
    // Front (_001, no hint) should beat rear (_005, rank=3 from h_images).
    expect(urls[0]).toBe(FULL(frontUnknown));
    expect(urls[1]).toBe(FULL(rearKnown));
  });

});
