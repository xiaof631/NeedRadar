import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5206,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3106',
        changeOrigin: true
      },
      '/health': {
        target: 'http://127.0.0.1:3106',
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return;
          }
          if (id.includes('element-plus')) {
            return 'ui-vendor';
          }
          if (
            id.includes('@tanstack/vue-query') ||
            id.includes('@vueuse') ||
            id.includes('axios')
          ) {
            return 'data-vendor';
          }
          if (id.includes('vue-i18n')) {
            return 'i18n-vendor';
          }
          if (id.includes('vue-router') || id.includes('pinia') || id.includes('/vue/')) {
            return 'vue-vendor';
          }
          return 'vendor';
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': '/src'
    }
  },
  test: {
    environment: 'happy-dom',
    setupFiles: ['./vitest.setup.ts']
  }
});
