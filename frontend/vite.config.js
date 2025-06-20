import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import vuetify from 'vite-plugin-vuetify'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true }), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      vue: 'vue/dist/vue.esm-bundler.js'
    }
  },
  server: {
    hmr: {
      // Reduce HMR aggressiveness during navigation
      overlay: false
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Separate auth-related modules to reduce HMR impact
          auth: ['./src/stores/auth.js', './src/services/auth.js']
        }
      }
    }
  }
})
