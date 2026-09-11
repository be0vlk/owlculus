/** Validate complete literals; the backend owns canonical persistence. */
export const ipAddressRule = (value) => {
  if (!value) return 'IP address is required'
  const invalid = 'Please enter a valid IPv4 or IPv6 address'
  const text = value.trim()
  if (text.includes(':')) {
    if (!/^[0-9a-f:.]+$/i.test(text)) return invalid
    try {
      // The browser URL parser validates an entire bracketed IPv6 literal.
      return new URL(`http://[${text}]/`).hostname.startsWith('[') || invalid
    } catch {
      return invalid
    }
  }
  const parts = text.split('.')
  return (
    (parts.length === 4 &&
      parts.every((part) => /^(0|[1-9][0-9]{0,2})$/.test(part) && Number(part) <= 255)) ||
    invalid
  )
}
