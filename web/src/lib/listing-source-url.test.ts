import { describe, expect, it } from "vitest";
import { listingSourceUrl } from "@/lib/listing-source-url";

describe("listingSourceUrl", () => {
  it("uses encar url from car data", () => {
    expect(
      listingSourceUrl({
        source: "encar",
        url: "http://www.encar.com/dc/dc_carddetailview.do?carid=123",
      }),
    ).toBe("http://www.encar.com/dc/dc_carddetailview.do?carid=123");
  });

  it("builds che168 detail url from listing id", () => {
    expect(
      listingSourceUrl({ source: "che168", inner_id: "5523456" }, "che168-5523456"),
    ).toBe("https://global.che168.com/detail/5523456");
  });

  it("prefers che168_vehicle_url when present", () => {
    expect(
      listingSourceUrl({
        source: "che168",
        che168_vehicle_url: "https://global.che168.com/detail/999",
        inner_id: "5523456",
      }),
    ).toBe("https://global.che168.com/detail/999");
  });

  it("builds autotrader vehicle url", () => {
    expect(
      listingSourceUrl({ source: "autotrader", inner_id: "789850281" }, "autotrader-789850281"),
    ).toBe("https://www.autotrader.com/cars-for-sale/vehicle/789850281");
  });

  it("prefers detail_url for autotrader", () => {
    expect(
      listingSourceUrl({
        source: "autotrader",
        detail_url: "https://www.autotrader.com/cars-for-sale/vehicle/1",
      }),
    ).toBe("https://www.autotrader.com/cars-for-sale/vehicle/1");
  });
});
