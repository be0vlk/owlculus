const contentDispositionHeader = (headers) => {
  if (!headers) return ''
  if (typeof headers.get === 'function') return headers.get('content-disposition') || ''
  return headers['content-disposition'] || headers['Content-Disposition'] || ''
}

const safeDownloadName = (filename, fallbackFilename) => {
  const leafName = (filename.split(/[\\/]/).pop() || '')
    .split('')
    .filter((character) => {
      const characterCode = character.charCodeAt(0)
      return characterCode >= 32 && characterCode !== 127
    })
    .join('')
  return leafName || fallbackFilename
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

export const createDownloadArtifact = (blob, headers) => ({ blob, headers })

export const downloadBlob = (artifact, fallbackFilename) => {
  const filename = getDownloadFilename(artifact.headers, fallbackFilename)
  const blob = artifact.blob
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}
