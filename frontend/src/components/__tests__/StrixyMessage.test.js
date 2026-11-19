import { expect, it, vi } from 'vitest'
import { mountWithVuetify } from './helpers/vuetify'
import StrixyMessage from '@/components/strixy/StrixyMessage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

const label = (message, props = {}) =>
  mountWithVuetify(StrixyMessage, { props: { message, ...props } })
    .find('.message-heading span')
    .text()

it('labels questions copied from a share as another participant', () => {
  const question = { role: 'user', content: 'Q', id: 'm1' }
  expect(label(question)).toBe('You')
  expect(label({ ...question, copied: true })).toBe('Conversation participant')
  expect(label(question, { shared: true })).toBe('Conversation participant')
})
