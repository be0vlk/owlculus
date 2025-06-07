// Time format utilities - standardized to UTC with 24-hour format
// My non-US friends, you can change the date format here to match your locale
// For example change en-US to en-GB and that's all you need to do!
// Note: Times are always displayed in UTC to ensure consistency across timezones

export function formatDate (dateString) {
  if (!dateString) return ''
  // Parse the datetime string directly - backend provides ISO format with timezone
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC'
  }).format(date).replace(',', '')
}

export function formatDateOnly (dateString) {
  if (!dateString) return ''
  // Parse the datetime string directly - backend provides ISO format with timezone
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'UTC'
  }).format(date)
}
