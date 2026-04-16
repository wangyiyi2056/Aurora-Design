import { expect, test } from 'vitest'
import { useGlobalStore } from './global-store'

test('default theme is dark', () => {
  const state = useGlobalStore.getState()
  expect(state.theme).toBe('dark')
})

test('toggle sidebar changes collapsed state', () => {
  const state = useGlobalStore.getState()
  expect(state.sidebarCollapsed).toBe(false)
  state.toggleSidebar()
  expect(useGlobalStore.getState().sidebarCollapsed).toBe(true)
})

test('setLanguage updates language', () => {
  const state = useGlobalStore.getState()
  state.setLanguage('en')
  expect(useGlobalStore.getState().language).toBe('en')
})
