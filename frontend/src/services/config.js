// This override is only for unusual development and test setups. Browser
// requests are same-origin by default because service paths begin with /api.
export const apiBaseURL = import.meta.env.VITE_API_BASE_URL || undefined
