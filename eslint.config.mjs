import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    // worker.js (Cloudflare Worker) and web/sim-worker.js are ES modules
    // running in a worker global scope, not a browser window.
    files: ["worker.js", "web/sim-worker.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.worker },
    },
  },
  {
    // Everything else under web/ is a plain classic script loaded by
    // <script> tags in the browser, sharing one global window scope.
    files: ["web/*.js"],
    ignores: ["web/sim-worker.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        ...globals.browser,
        // Attached to `window` by web/sim-client.js and
        // web/wowsims-import.js respectively; consumed by sibling
        // classic scripts that load after them in the page.
        ForeverSim: "readonly",
        WowSimsImport: "readonly",
      },
    },
    rules: {
      // Multiple scripts intentionally share top-level names via window.
      "no-redeclare": "off",
    },
  },
  {
    // A Node CLI script (run via `node tools/stamp_version.js`), not a
    // browser or worker script.
    files: ["tools/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "commonjs",
      globals: { ...globals.node },
    },
  },
  {
    ignores: ["web/data/**", "web/item-icons/**", "web/talent-icons/**", "web/engine/**", "node_modules/**"],
  },
];
