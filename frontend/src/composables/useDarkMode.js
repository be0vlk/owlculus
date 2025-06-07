import { ref, onMounted } from 'vue'
import { useTheme } from 'vuetify'

const LOCAL_STORAGE_KEY = 'color-scheme'

// Create a single source of truth for dark mode state
const isDark = ref(false)

// Initialize dark mode state
const initDarkMode = () => {
  const storedTheme = localStorage.getItem(LOCAL_STORAGE_KEY)
  if (storedTheme !== null) {
    return storedTheme === 'dark'
  }
  // Default to system preference if no stored preference
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
}

export const useDarkMode = () => {
  const theme = useTheme()

  const setDarkMode = (dark) => {
    isDark.value = dark
    localStorage.setItem(LOCAL_STORAGE_KEY, dark ? 'dark' : 'light')

    // Update Vuetify theme
    theme.global.name.value = dark ? 'owlculusDark' : 'owlculusLight'
  }

  const toggleDark = () => {
    setDarkMode(!isDark.value)
  }

  onMounted(() => {
    // Initialize theme based on persisted preference or system preference
    const darkMode = initDarkMode()
    setDarkMode(darkMode)

    // Watch for system theme changes only if no explicit user choice
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      const handleChange = (e) => {
        if (localStorage.getItem(LOCAL_STORAGE_KEY) === null) {
          setDarkMode(e.matches)
        }
      }

      mediaQuery.addEventListener('change', handleChange)
    }
  })

  return {
    isDark,
    toggleDark,
    setDarkMode,
  }
}
