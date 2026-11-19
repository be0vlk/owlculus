const contentDispositionHeader = (headers) => {
  if (!headers) return ''
  if (typeof headers.get === 'function') return headers.get('content-disposition') || ''
  return headers['content-disposition'] || headers['Content-Disposition'] || ''
}

const safeDownloadName = (filename, fallbackFilename) => {
  // Strip any directory part and control characters.
  return filename.replace(/^.*[\\/]|\p{Cc}/gsu, '') || fallbackFilename
}

export const getDownloadFilename = (headers, fallbackFilename) => {
  const header = contentDispositionHeader(headers)
  const encodedMatch = header.match(/filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i)
  if (encodedMatch) {
    try {
      return safeDownloadName(
        decodeURIComponent(encodedMatch[1].trim().replace(/^"|"$/g, '')),
        fallbackFilename,
      )
    } catch {
      // Fall through to the plain filename or caller-provided fallback.
    }
  }

  const plainMatch = header.match(/filename\s*=\s*(?:"([^"]+)"|([^;]+))/i)
  const filename = plainMatch?.[1] || plainMatch?.[2]?.trim()
  return filename ? safeDownloadName(filename, fallbackFilename) : fallbackFilename
}

export const downloadBlob = (artifact, fallbackFilename) => {
  const url = URL.createObjectURL(artifact.blob)
  const download = getDownloadFilename(artifact.headers, fallbackFilename)
  Object.assign(document.createElement('a'), { href: url, download }).click()
  URL.revokeObjectURL(url)
}
