import { nextTick, watch } from 'vue'

export function useDialogFocusRestore(isOpen) {
  let activator = null

  watch(
    isOpen,
    (open, wasOpen) => {
      if (typeof document === 'undefined') return

      if (open) {
        const activeElement = document.activeElement
        activator = activeElement !== document.body && activeElement?.focus ? activeElement : null
        return
      }

      if (wasOpen && activator) {
        const elementToRestore = activator
        activator = null
        nextTick(() => {
          if (elementToRestore.isConnected) elementToRestore.focus()
        })
      }
    },
    { flush: 'pre' },
  )
}
