// @ts-check
/**
 * Geometric layout asserts for catalog UI e2e (overflow / clip / hit-target).
 */

/**
 * @param {import('@playwright/test').Locator} locator
 * @param {{ minW?: number, minH?: number }} [opts]
 */
export async function expectVisibleBox(locator, opts = {}) {
  const minW = opts.minW ?? 8;
  const minH = opts.minH ?? 8;
  await locator.waitFor({ state: "visible" });
  const box = await locator.boundingBox();
  if (!box) throw new Error("element has no bounding box");
  if (box.width < minW || box.height < minH) {
    throw new Error(
      `hit-target too small: ${box.width.toFixed(1)}×${box.height.toFixed(1)} (min ${minW}×${minH})`,
    );
  }
  return box;
}

/**
 * Element fully inside the layout viewport (not just intersection).
 * @param {import('@playwright/test').Page} page
 * @param {import('@playwright/test').Locator} locator
 * @param {{ pad?: number }} [opts]
 */
export async function expectInViewport(page, locator, opts = {}) {
  const pad = opts.pad ?? 0;
  const box = await expectVisibleBox(locator);
  const vp = page.viewportSize();
  if (!vp) throw new Error("no viewport size");
  if (box.x < -pad || box.y < -pad) {
    throw new Error(`element starts outside viewport: x=${box.x} y=${box.y}`);
  }
  if (box.x + box.width > vp.width + pad || box.y + box.height > vp.height + pad) {
    throw new Error(
      `element overflows viewport: box=${JSON.stringify(box)} vp=${JSON.stringify(vp)}`,
    );
  }
  return box;
}

/**
 * Trigger label text is not clipped horizontally (scrollWidth ≤ clientWidth).
 * @param {import('@playwright/test').Locator} locator
 */
export async function expectTextNotClipped(locator) {
  const metrics = await locator.evaluate((el) => {
    const target =
      el.querySelector("[data-slot=button],button,span") ||
      el;
    return {
      scrollWidth: target.scrollWidth,
      clientWidth: target.clientWidth,
      scrollHeight: target.scrollHeight,
      clientHeight: target.clientHeight,
    };
  });
  if (metrics.scrollWidth > metrics.clientWidth + 1) {
    throw new Error(
      `text clipped horizontally: scrollWidth=${metrics.scrollWidth} clientWidth=${metrics.clientWidth}`,
    );
  }
  return metrics;
}

/**
 * Parent container must not have horizontal overflow (scrollWidth ≈ clientWidth).
 * @param {import('@playwright/test').Locator} locator
 */
export async function expectNoHorizontalOverflow(locator) {
  const metrics = await locator.evaluate((el) => ({
    scrollWidth: el.scrollWidth,
    clientWidth: el.clientWidth,
  }));
  if (metrics.scrollWidth > metrics.clientWidth + 2) {
    throw new Error(
      `horizontal overflow: scrollWidth=${metrics.scrollWidth} clientWidth=${metrics.clientWidth}`,
    );
  }
  return metrics;
}

/**
 * Hover must not shift the element's box (layout jump).
 * @param {import('@playwright/test').Page} page
 * @param {import('@playwright/test').Locator} locator
 * @param {{ tolerance?: number }} [opts]
 */
export async function expectHoverStable(page, locator, opts = {}) {
  const tolerance = opts.tolerance ?? 1.5;
  await locator.scrollIntoViewIfNeeded();
  const before = await expectVisibleBox(locator, { minW: 24, minH: 24 });
  await locator.hover({ force: true });
  await page.waitForTimeout(80);
  const after = await locator.boundingBox();
  if (!after) throw new Error("element disappeared on hover");
  const dx = Math.abs(after.x - before.x);
  const dy = Math.abs(after.y - before.y);
  const dw = Math.abs(after.width - before.width);
  const dh = Math.abs(after.height - before.height);
  if (dx > tolerance || dy > tolerance || dw > tolerance || dh > tolerance) {
    throw new Error(
      `hover shifted layout: before=${JSON.stringify(before)} after=${JSON.stringify(after)}`,
    );
  }
  return { before, after };
}

/**
 * Dropdown/popover content is inside viewport and has usable size.
 * @param {import('@playwright/test').Page} page
 * @param {import('@playwright/test').Locator} content
 */
export async function expectMenuInViewport(page, content) {
  await content.waitFor({ state: "visible" });
  return expectInViewport(page, content, { pad: 8 });
}
