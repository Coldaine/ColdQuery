import { defineConfig, configDefaults } from "vitest/config";

export default defineConfig({
  test: {
    exclude: [...configDefaults.exclude, "_comparison/**"],
    coverage: {
      provider: "v8",
      exclude: ["**/__tests__/**", "**/node_modules/**"],
    },
  },
});
