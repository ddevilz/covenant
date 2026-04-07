import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
  resolve: {
    alias: {
      "covenant-sdk": new URL("./src/index.ts", import.meta.url).pathname,
    },
  },
});
