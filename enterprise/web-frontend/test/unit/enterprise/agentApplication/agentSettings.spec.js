import { snapStyle } from '@baserow_enterprise/utils/agentSettings'

describe('snapStyle', () => {
  test('snaps temperatures to the nearest style', () => {
    expect(snapStyle(0.1)).toBe('precise')
    expect(snapStyle('0.1')).toBe('precise')
    expect(snapStyle(0.3)).toBe('precise')
    expect(snapStyle(0.5)).toBe('balanced')
    expect(snapStyle(0.7)).toBe('balanced')
    expect(snapStyle(0.8)).toBe('creative')
    expect(snapStyle(1)).toBe('creative')
    expect(snapStyle(1.5)).toBe('creative')
    expect(snapStyle(null)).toBe('precise')
    expect(snapStyle(undefined)).toBe('precise')
  })
})
