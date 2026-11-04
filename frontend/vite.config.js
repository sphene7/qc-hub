import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const backendTarget = process.env.VITE_DEV_BACKEND || "http://127.0.0.1:8001";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 8088,
    strictPort: true,
    // Windows + 中文路径下 chokidar 偶尔漏事件，改用轮询保证改动即时生效
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});

console.log("[vite] API proxy →", backendTarget);
