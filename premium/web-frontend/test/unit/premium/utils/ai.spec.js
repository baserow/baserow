import { getAIFieldStatus } from '@baserow_premium/utils/ai'

describe('getAIFieldStatus', () => {
  test('returns status from valid metadata', () => {
    const row = {
      _: { metadata: { ai_field: { 42: { status: 'generating' } } } },
    }
    expect(getAIFieldStatus(row, 42)).toBe('generating')
  })

  test('returns null when row._ is undefined', () => {
    expect(getAIFieldStatus({}, 42)).toBeNull()
  })

  test('returns null when metadata is missing', () => {
    expect(getAIFieldStatus({ _: {} }, 42)).toBeNull()
  })

  test('returns null when ai_field key is missing', () => {
    expect(getAIFieldStatus({ _: { metadata: {} } }, 42)).toBeNull()
  })

  test('returns null when field id is not present', () => {
    const row = {
      _: { metadata: { ai_field: { 99: { status: 'error' } } } },
    }
    expect(getAIFieldStatus(row, 42)).toBeNull()
  })

  test('returns null when status key is missing from field metadata', () => {
    const row = {
      _: { metadata: { ai_field: { 42: { other: 'value' } } } },
    }
    expect(getAIFieldStatus(row, 42)).toBeNull()
  })
})
