// My non-US friends, you can change the date format here to match your locale
// For example change en-US to en-GB and that's all you need to do!

export function formatDate(dateString) {
  if (!dateString) return ''
  // Handle UTC timestamps properly - add 'Z' if not present to indicate UTC
  const utcDateString = dateString.includes('Z') ? dateString : `${dateString}Z`
  const date = new Date(utcDateString)
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date).replace(',', '')
}

export function formatDateOnly(dateString) {
  if (!dateString) return ''
  // Handle UTC timestamps properly - add 'Z' if not present to indicate UTC
  const utcDateString = dateString.includes('Z') ? dateString : `${dateString}Z`
  const date = new Date(utcDateString)
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date)
}
