const path = require("node:path");
const tailwindPostcss = require("@tailwindcss/postcss");
const { mergeConfig } = require("vite");

/** @type {import("@storybook/react-vite").StorybookConfig} */
module.exports = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-essentials", "@storybook/addon-a11y"],
  framework: { name: "@storybook/react-vite", options: {} },
  staticDirs: ["../public"],
  async viteFinal(config) {
    return mergeConfig(config, {
      css: {
        postcss: {
          plugins: [tailwindPostcss()],
        },
      },
      resolve: {
        alias: {
          "@": path.resolve(__dirname, "../src"),
        },
      },
    });
  },
};
