export const copyToClipboard = (text) =>
  navigator.clipboard.writeText(text).catch((err) => console.error('Failed to copy text:', err))
