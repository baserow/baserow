import {
  markRealtimeMetadata,
  realtimeMetadata,
} from '@baserow/modules/core/utils/realtime'

describe('realtime metadata utils', () => {
  test('realtimeMetadata returns the default tracking fields', () => {
    expect(realtimeMetadata()).toEqual({
      viaRealtime: false,
      realtimeVersion: 0,
    })
  })

  test('a realtime update flags the item and bumps the version', () => {
    const item = { _: { ...realtimeMetadata() } }

    markRealtimeMetadata(item, true)
    expect(item._.viaRealtime).toBe(true)
    expect(item._.realtimeVersion).toBe(1)

    markRealtimeMetadata(item, true)
    expect(item._.viaRealtime).toBe(true)
    expect(item._.realtimeVersion).toBe(2)
  })

  test('a local update clears the flag without bumping the version', () => {
    const item = { _: { viaRealtime: true, realtimeVersion: 3 } }

    markRealtimeMetadata(item, false)
    expect(item._.viaRealtime).toBe(false)
    expect(item._.realtimeVersion).toBe(3)
  })

  test('defaults to a local update when viaRealtime is omitted', () => {
    const item = { _: { viaRealtime: true, realtimeVersion: 1 } }

    markRealtimeMetadata(item)
    expect(item._.viaRealtime).toBe(false)
    expect(item._.realtimeVersion).toBe(1)
  })

  test('is a no-op for items without metadata', () => {
    expect(() => markRealtimeMetadata({})).not.toThrow()
    expect(() => markRealtimeMetadata(null)).not.toThrow()
    expect(() => markRealtimeMetadata(undefined)).not.toThrow()
  })
})
