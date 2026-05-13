import { describe, expect, test } from 'vitest'
import i18n, { supportedLanguages } from './i18n'

describe('i18n resources', () => {
  test('loads translations from src i18n language packs', () => {
    expect(supportedLanguages).toContain('zh-CN')
    expect(supportedLanguages).toContain('en')

    expect(i18n.getResource('zh-CN', 'common', 'app.brand')).toBe('Aurora Design')
    expect(i18n.getResource('en', 'common', 'chat.startTitle')).toBe('Start a conversation')
  })

  test('keeps legacy Aurora Design translation keys available without public locale JSON', () => {
    expect(i18n.getResource('zh-CN', 'common', 'appName')).toBe('Aurora Design')
    expect(i18n.getResource('zh-CN', 'chat', 'chat.welcomeTitle')).toBe('欢迎使用 Aurora Design')
    expect(i18n.getResource('en', 'construct', 'models.testSuccess')).toBe('Connection test passed')
  })
})
