import { describe, expect, it } from "vitest";
import { getAllCarPhotoUrls } from "./car-gallery-images";
import { normalizeEncarPhotoUrl } from "./car-images";

const FRONT = "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_001.jpg";
const REAR = "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_009.jpg";
const SIDE = "https://ci.encar.com/carpicture/carpicture08/pic4278/42789943_003.jpg";
const FULL = (url: string) => `${url}?impolicy=widthRate&rw=1920`;

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

  it("falls back to h_images as full-size URLs when images[] is empty", () => {
    const urls = getAllCarPhotoUrls({
      source: "encar",
      h_images: [{ path: "/carpicture08/pic4278/42789943_001.jpg", type: "EXT", desc: "전면" }],
    });
    expect(urls[0]).toBe(FULL(FRONT));
    expect(urls[0]).not.toContain("wtmk=");
  });
});
