export const copyToClipboard = async (text) => {
  try {
    // navigator.clipboard is undefined outside secure contexts (plain http).
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}
