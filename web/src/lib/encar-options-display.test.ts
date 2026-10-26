import { describe, expect, it } from "vitest";
import {
  displayEncarStandardOption,
  labelsFromEncarChoicePhotos,
  labelsFromEncarStandardCodes,
} from "@/lib/encar-options-display";
import { collectCarEquipmentLabels } from "@/lib/car-equipment-labels";

/** Реальные коды Encar 42789943 (Cruze 1.4 LTZ). */
const CRUZE_STANDARD = [
  "001",
  "003",
  "006",
  "007",
  "008",
  "014",
  "015",
  "017",
  "019",
  "020",
  "022",
  "024",
  "026",
  "027",
  "031",
  "032",
  "033",
  "055",
  "056",
  "057",
  "068",
  "071",
  "072",
  "081",
  "096",
  "097",
];

describe("Encar standard option codes", () => {
  it("maps official Encar codes instead of the invented 1=smart-key table", () => {
    expect(displayEncarStandardOption("057")).toBe("Смарт-ключ");
    expect(displayEncarStandardOption("010")).toBe("Люк");
    expect(displayEncarStandardOption("068")).toBe("Круиз-контроль");
    expect(displayEncarStandardOption("079")).toBe("Адаптивный круиз-контроль");
    expect(displayEncarStandardOption("001")).toBe("ABS");
  });

  it("keeps only present options for the Cruze listing 42789943", () => {
    const labels = labelsFromEncarStandardCodes(CRUZE_STANDARD);
    expect(labels).toContain("Смарт-ключ");
    expect(labels).toContain("Круиз-контроль");
    expect(labels).toContain("Кожаные сиденья");
    expect(labels).toContain("Подогрев передних сидений");
    expect(labels).toContain("Электроскладывание зеркал");
    expect(labels).toContain("Bluetooth");
    expect(labels).not.toContain("Адаптивный круиз-контроль");
    expect(labels).not.toContain("Панорамная крыша / люк");
    expect(labels).not.toContain("Память сиденья пассажира");
    expect(labels).not.toContain("Камера заднего вида");
    expect(labels).not.toContain("Светодиодные фары");
    expect(labelsFromEncarStandardCodes(["999"])).toEqual([]);
  });

  it("does not treat sellingpoint catalog rows as installed options", () => {
    const labels = collectCarEquipmentLabels({
      source: "encar",
      options: { standard: ["057", "014"] },
      extra: {
        sellingpoint: {
          uniqueOptionPhotos: [
            { partCode: "SPEC_bodyTypeNm", partName: "바디타입(세단)", optionCode: "010" },
            { optionCode: "079", partName: "어댑티브 크루즈", name: "Адаптивный круиз-контроль" },
          ],
          choiceOptionPhotos: [{ partCode: "10003", partName: "프리미엄 초이스" }],
        },
      },
    });
    expect(labels).toContain("Смарт-ключ");
    expect(labels).toContain("Кожаные сиденья");
    expect(labels).toContain("프리미엄 초이스");
    expect(labels).not.toContain("Адаптивный круиз-контроль");
    expect(labels).not.toContain("Люк");
  });

  it("skips SPEC_ rows from choice photos", () => {
    expect(
      labelsFromEncarChoicePhotos([
        { partCode: "SPEC_fuelNm", partName: "연료(가솔린)" },
        { partCode: "10003", partName: "프리미엄 초이스" },
      ]),
    ).toEqual(["프리미엄 초이스"]);
  });
});
