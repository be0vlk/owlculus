/**
 * Composable for managing folder icon colors consistently across the application
 * Uses Vuetify theme colors for consistency
 */
export function useFolderIcons() {
  // Centralized folder icon colors using Vuetify theme colors
  const folderColors = {
    primary: 'purple-darken-1',
    secondary: 'purple-lighten-1',
    light: 'purple-lighten-3',
  }

  /**
   * Get the appropriate folder color based on context
   * @param {string|number} level - The folder level or context ('primary', 'secondary', 'light', or number)
   * @returns {string} The Vuetify color class
   */
  const getFolderColor = (level = 'primary') => {
    if (typeof level === 'number') {
      return level === 0 ? folderColors.primary : folderColors.secondary
    }
    return folderColors[level] || folderColors.primary
  }

  /**
   * Get folder icon based on state
   * @param {boolean} isOpen - Whether the folder is open/expanded
   * @param {boolean} isOutline - Whether to use outline variant
   * @returns {string} The MDI icon name
   */
  const getFolderIcon = (isOpen = false, isOutline = false) => {
    if (isOutline) return 'mdi-folder-outline'
    return isOpen ? 'mdi-folder-open' : 'mdi-folder'
  }

  return {
    folderColors,
    getFolderColor,
    getFolderIcon,
  }
}
