import { ref } from 'vue'

export const useDarkMode = () => {
  const isDark = ref(document.documentElement.classList.contains('dark'))

  const toggleDark = () => {
    isDark.value = !isDark.value
    
    if (isDark.value) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('color-scheme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('color-scheme', 'light')
    }
  }

  // Initialize from localStorage
  const storedTheme = localStorage.getItem('color-scheme')
  if (storedTheme === 'dark') {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }

  return {
    isDark,
    toggleDark
  }
}
