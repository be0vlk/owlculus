// Autosave and explicit saves share one ordered stream of writes per editor.
export function useNoteSaveQueue({ saving, saveError, lastSaved, lastSavedTime }) {
  let pending = null
  let pendingContent

  const save = (content, persist, { force = false } = {}) => {
    if (!force && pending && content === pendingContent) return pending

    const previous = pending
    const request = (async () => {
      if (previous) await previous.catch(() => {})
      if (!force && content === lastSaved.value) return

      saving.value = true
      saveError.value = ''
      try {
        const result = await persist()
        lastSaved.value = content
        lastSavedTime.value = new Date()
        return result
      } catch (error) {
        saveError.value = 'Failed to save notes. Your changes are still in the editor.'
        throw error
      } finally {
        saving.value = false
      }
    })()

    pendingContent = content
    pending = request
    const clearPending = () => {
      if (pending === request) pending = null
    }
    request.then(clearPending, clearPending)
    return request
  }

  return { save }
}
