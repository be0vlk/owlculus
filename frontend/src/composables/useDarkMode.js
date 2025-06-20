import { ref, onMounted, onUnmounted } from 'vue'
import { useTheme } from 'vuetify'

const LOCAL_STORAGE_KEY = 'color-scheme'

// Singleton state - shared across all component instances
const isDark = ref(false)
let isInitialized = false
let mediaQuery = null
let handleChange = null

// Initialize dark mode state
const initDarkMode = () => {
  const storedTheme = localStorage.getItem(LOCAL_STORAGE_KEY)
  if (storedTheme !== null) {
    return storedTheme === 'dark'
  }
  // Default to system preference if no stored preference
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
}

// Singleton initialization
const initializeDarkMode = (theme) => {
  if (isInitialized) return

  // Initialize theme based on persisted preference or system preference
  const darkMode = initDarkMode()
  isDark.value = darkMode
  localStorage.setItem(LOCAL_STORAGE_KEY, darkMode ? 'dark' : 'light')
  theme.global.name.value = darkMode ? 'owlculusDark' : 'owlculusLight'

  // Watch for system theme changes only if no explicit user choice
  if (window.matchMedia) {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    handleChange = (e) => {
      if (localStorage.getItem(LOCAL_STORAGE_KEY) === null) {
        isDark.value = e.matches
        localStorage.setItem(LOCAL_STORAGE_KEY, e.matches ? 'dark' : 'light')
        theme.global.name.value = e.matches ? 'owlculusDark' : 'owlculusLight'
      }
    }

    mediaQuery.addEventListener('change', handleChange)
  }

  isInitialized = true
}

// Cleanup function
const cleanup = () => {
  if (mediaQuery && handleChange) {
    mediaQuery.removeEventListener('change', handleChange)
  }
}

export const useDarkMode = () => {
  const theme = useTheme()

  const setDarkMode = (dark) => {
    isDark.value = dark
    localStorage.setItem(LOCAL_STORAGE_KEY, dark ? 'dark' : 'light')
    theme.global.name.value = dark ? 'owlculusDark' : 'owlculusLight'
  }

  const toggleDark = () => {
    setDarkMode(!isDark.value)
  }

  onMounted(() => {
    initializeDarkMode(theme)
  })

  onUnmounted(() => {
    // Only cleanup when all components using this composable are unmounted
    // This is a simple approach - could be improved with reference counting
    cleanup()
  })

  return {
    isDark,
    toggleDark,
    setDarkMode
  }
}
