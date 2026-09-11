import { nextTick, watch } from 'vue'

export function useDialogFocusRestore(isOpen, restoreFocusTo = null) {
  let activator = null

  const resolveConfiguredTarget = () =>
    typeof restoreFocusTo === 'function' ? restoreFocusTo() : restoreFocusTo

  watch(
    isOpen,
    (open, wasOpen) => {
      if (typeof document === 'undefined') return

      if (open) {
        const activeElement = document.activeElement
        const configuredTarget = resolveConfiguredTarget()
        activator =
          configuredTarget ||
          (activeElement !== document.body && activeElement?.focus ? activeElement : null)
        return
      }

      if (wasOpen && activator) {
        const capturedActivator = activator
        activator = null
        nextTick(() => {
          const configuredTarget = resolveConfiguredTarget()
          const elementToRestore = configuredTarget?.isConnected
            ? configuredTarget
            : capturedActivator
          if (elementToRestore.isConnected) elementToRestore.focus()
        })
      }
    },
    { flush: 'pre', immediate: true },
  )
}
