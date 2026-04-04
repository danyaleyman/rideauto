const fs = require('fs');
const path = require('path');

const carHtmlPath = path.join(__dirname, 'frontend', 'car.html');
const carHtmlForScan = fs
  .readFileSync(carHtmlPath, 'utf8')
  .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [{ raw: carHtmlForScan, extension: 'html' }],
  // Ложные совпадения из JS/CSS (например `if (!block)`, `position: fixed`, `ease-in-out` в keyframes).
  blocklist: ['static', 'fixed', 'resize', '!block', 'hidden', 'filter', 'ease-in-out', 'table'],
  theme: {
    extend: {},
  },
  plugins: [],
};
