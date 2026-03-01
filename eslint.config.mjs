import js from "@eslint/js";

const browserGlobals = {
  window: "readonly",
  document: "readonly",
  navigator: "readonly",
  location: "readonly",
  fetch: "readonly",
  WebSocket: "readonly",
  performance: "readonly",
  requestAnimationFrame: "readonly",
  cancelAnimationFrame: "readonly",
  setTimeout: "readonly",
  clearTimeout: "readonly",
  setInterval: "readonly",
  clearInterval: "readonly",
  console: "readonly",
  URL: "readonly",
  ForceGraph3D: "readonly",
  THREE: "readonly",
};

const nodeGlobals = {
  console: "readonly",
  process: "readonly",
  fetch: "readonly",
  URL: "readonly",
  __dirname: "readonly",
  __filename: "readonly",
  module: "readonly",
  require: "readonly",
};

export default [
  {
    ignores: ["convex/_generated/**", "node_modules/**", "venv/**"],
  },
  js.configs.recommended,
  {
    files: ["frontend/**/*.js"],
    languageOptions: {
      globals: browserGlobals,
      sourceType: "script",
    },
    rules: {
      "no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],
    },
  },
  {
    files: ["scripts/**/*.js"],
    languageOptions: {
      globals: nodeGlobals,
      sourceType: "commonjs",
    },
    rules: {
      "no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],
    },
  },
];
