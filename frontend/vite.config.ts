import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// In development the Django API runs on :8000; in production Django serves the built app.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
});
