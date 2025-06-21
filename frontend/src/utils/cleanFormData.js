// utils/cleanFormData.js
export function cleanFormData(data) {
  const cleanedData = { ...data }
  for (const key in cleanedData) {
    if (cleanedData[key] === '' || cleanedData[key] === null) {
      delete cleanedData[key]
    } else if (Array.isArray(cleanedData[key])) {
      // Keep arrays as is if they have items, remove if empty
      if (cleanedData[key].length === 0) {
        delete cleanedData[key]
      }
    } else if (typeof cleanedData[key] === 'object') {
      cleanedData[key] = cleanFormData(cleanedData[key]) // Recursively clean nested objects
      if (Object.keys(cleanedData[key]).length === 0) {
        delete cleanedData[key]
      }
    }
  }
  return cleanedData
}
