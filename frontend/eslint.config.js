import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import pluginVitest from '@vitest/eslint-plugin'
import pluginPlaywright from 'eslint-plugin-playwright'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import pluginVuetify from 'eslint-plugin-vuetify'

const [vuetifyBaseConfig, vuetifyMigrationConfig] = pluginVuetify.configs['flat/recommended-v4']

export default [
  {
    name: 'app/files-to-lint',
    files: ['**/*.{js,mjs,jsx,vue}'],
  },

  {
    name: 'app/files-to-ignore',
    ignores: ['**/dist/**', '**/dist-ssr/**', '**/coverage/**'],
  },

  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  {
    ...vuetifyBaseConfig,
    plugins: {
      vuetify: vuetifyBaseConfig.plugins.vuetify,
    },
  },
  vuetifyMigrationConfig,

  {
    name: 'app/browser-globals',
    languageOptions: {
      globals: {
        localStorage: 'readonly',
        window: 'readonly',
      },
    },
  },

  {
    ...pluginVitest.configs.recommended,
    files: ['src/**/__tests__/*'],
  },

  {
    ...pluginPlaywright.configs['flat/recommended'],
    files: ['e2e/**/*.{test,spec}.{js,ts,jsx,tsx}'],
  },
  skipFormatting,
]
