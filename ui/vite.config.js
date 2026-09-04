import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendUrl = process.env.VITE_API_URL || 'http://localhost:8000';
const wsTarget = backendUrl.replace(/^http/, 'ws');

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT || '3000', 10),
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        timeout: 120000,
        proxyTimeout: 120000,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});