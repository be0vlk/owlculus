// Time format utilities - standardized to UTC with 24-hour format
// Change the locale here to match a different date format.
// For example change en-US to en-GB and that's all you need to do!
// Note: Times are always displayed in UTC to ensure consistency across timezones

const DATE_PARTS = { year: 'numeric', month: '2-digit', day: '2-digit' }

const utcFormatter = (options) => {
  const format = new Intl.DateTimeFormat('en-US', { ...options, timeZone: 'UTC' })
  // Backend provides ISO datetime strings with timezone
  return (dateString) => (dateString ? format.format(new Date(dateString)) : '')
}

const formatWithTime = utcFormatter({
  ...DATE_PARTS,
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export const formatDate = (dateString) => formatWithTime(dateString).replace(',', '')
export const formatDateOnly = utcFormatter(DATE_PARTS)
