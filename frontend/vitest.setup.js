import { config } from '@vue/test-utils'

// Fail at the source: "Failed to resolve component: v-col" beats "Cannot call props on an empty VueWrapper".
config.global.config.warnHandler = (msg, instance, trace) => {
  // Vue rethrows the real error right after this warning; throwing here would hide it.
  if (msg.startsWith('Unhandled error')) return
  throw new Error(`[Vue warn]: ${msg}${trace}`)
}
