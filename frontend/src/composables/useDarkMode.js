import { ref } from 'vue'
import { useTheme } from 'vuetify'

const STORAGE_KEY = 'color-scheme'
const stored = localStorage.getItem(STORAGE_KEY)
const isDark = ref(
  stored ? stored === 'dark' : !!window.matchMedia?.('(prefers-color-scheme: dark)').matches,
)

export const useDarkMode = () => {
  const theme = useTheme()
  const apply = () => theme.change(isDark.value ? 'owlculusDark' : 'owlculusLight')
  apply()

  const toggleDark = () => {
    isDark.value = !isDark.value
    localStorage.setItem(STORAGE_KEY, isDark.value ? 'dark' : 'light')
    apply()
  }

  return { isDark, toggleDark }
}
