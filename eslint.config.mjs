import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["frontend/js/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...globals.browser,
        Swiper: "readonly",
        TELEGRAM_MANAGER_URL: "readonly",
        WRAAuthFavorites: "readonly",
        anime: "readonly",
        Splitting: "readonly",
      },
    },
    rules: {
      "no-unused-vars": [
        "warn",
        { varsIgnorePattern: "^_", argsIgnorePattern: "^_", caughtErrors: "none" },
      ],
      "no-prototype-builtins": "off",
      "no-empty": "off",
      "no-redeclare": "off",
      "no-useless-escape": "warn",
    },
  },
];
