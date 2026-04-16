import { expect, test, beforeEach } from 'vitest'
import { useChatStore } from './chat-store'

beforeEach(() => {
  useChatStore.getState().resetChat()
})

test('addMessage appends to messages', () => {
  const state = useChatStore.getState()
  state.addMessage({ role: 'user', content: 'hello' })
  expect(useChatStore.getState().messages).toHaveLength(2) // system + user
})

test('resetChat clears non-system messages', () => {
  useChatStore.getState().addMessage({ role: 'user', content: 'hello' })
  useChatStore.getState().resetChat()
  expect(useChatStore.getState().messages).toHaveLength(1)
  expect(useChatStore.getState().messages[0].role).toBe('system')
})
