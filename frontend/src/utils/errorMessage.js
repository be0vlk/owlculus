export function getErrorMessage(error, fallback) {
  return (
    error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback
  )
}
