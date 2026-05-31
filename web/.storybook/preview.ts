import type { Preview } from "@storybook/react";

import "../src/app/globals.css";

const preview: Preview = {
  parameters: {
    layout: "padded",
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      // В dev/storybook — предупреждения; в CI e2e/a11y.spec.js — жёсткий гейт (serious+).
      test: "warn",
    },
  },
};

export default preview;
