import { fileURLToPath, URL } from 'node:url'
import process from 'node:process'

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
      vue: 'vue/dist/vue.esm-bundler.js',
    },
  },
  optimizeDeps: {
    include: [
      'vuetify/components/VAlert',
      'vuetify/components/VApp',
      'vuetify/components/VAvatar',
      'vuetify/components/VBtn',
      'vuetify/components/VBtnGroup',
      'vuetify/components/VBtnToggle',
      'vuetify/components/VCard',
      'vuetify/components/VCheckbox',
      'vuetify/components/VChip',
      'vuetify/components/VChipGroup',
      'vuetify/components/VCombobox',
      'vuetify/components/VDataTable',
      'vuetify/components/VDialog',
      'vuetify/components/VDivider',
      'vuetify/components/VExpansionPanel',
      'vuetify/components/VForm',
      'vuetify/components/VGrid',
      'vuetify/components/VIcon',
      'vuetify/components/VImg',
      'vuetify/components/VLabel',
      'vuetify/components/VList',
      'vuetify/components/VMain',
      'vuetify/components/VMenu',
      'vuetify/components/VNavigationDrawer',
      'vuetify/components/VProgressCircular',
      'vuetify/components/VProgressLinear',
      'vuetify/components/VRadio',
      'vuetify/components/VRadioGroup',
      'vuetify/components/VSelect',
      'vuetify/components/VSkeletonLoader',
      'vuetify/components/VSlider',
      'vuetify/components/VSnackbar',
      'vuetify/components/VSwitch',
      'vuetify/components/VTable',
      'vuetify/components/VTabs',
      'vuetify/components/VTextField',
      'vuetify/components/VTextarea',
      'vuetify/components/VTimeline',
      'vuetify/components/VToolbar',
      'vuetify/components/VTooltip',
      'vuetify/components/VWindow',
      'vuetify/components/transitions',
      'vuetify/components/VTreeview',
    ],
  },
  server: {
    host: '0.0.0.0',
    cors: false,
    hmr: {
      // Reduce HMR aggressiveness during navigation
      overlay: false,
    },
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        xfwd: true,
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Separate auth-related modules to reduce HMR impact
          auth: ['./src/stores/auth.js', './src/services/auth.js'],
        },
      },
    },
  },
})
