import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest'

import {
  createPresenceFocusSender,
  resolvePresencePageParams,
  tablePresenceSpaceName,
} from '@baserow/modules/database/utils/presence'

function mockRealtime() {
  return { sendFocus: vi.fn() }
}

describe('tablePresenceSpaceName', () => {
  test('formats table id into space name', () => {
    expect(tablePresenceSpaceName(42)).toBe('table-42')
  })
})

function mockOwnershipType({
  supportsPresenceFocus = true,
  page,
  params,
} = {}) {
  return {
    enhanceRealtimePagePayload(_db, _table, _view, payload) {
      if (page) {
        payload.page = page
        payload.params = params
      }
      return payload
    },
    supportsPresenceFocus() {
      return supportsPresenceFocus
    },
  }
}

function mockRegistry(ownershipType) {
  return {
    get(type, name) {
      if (type === 'viewOwnershipType') return ownershipType
      throw new Error(`Unknown registry type: ${type}`)
    },
  }
}

describe('resolvePresencePageParams', () => {
  test('returns focusEnabled true for collaborative view', () => {
    const ot = mockOwnershipType()
    const registry = mockRegistry(ot)
    const result = resolvePresencePageParams(
      registry,
      { workspace: { id: 1 } },
      { id: 42 },
      { ownership_type: 'collaborative' }
    )
    expect(result).toEqual({
      page: 'table',
      params: { table_id: 42 },
      spaceName: 'table-42',
      focusEnabled: true,
    })
  })

  test('returns focusEnabled false when ownership type disables focus', () => {
    const ot = mockOwnershipType({
      supportsPresenceFocus: false,
      page: 'restricted_view',
      params: { restricted_view_id: 7, table_id: 42 },
    })
    const registry = mockRegistry(ot)
    const result = resolvePresencePageParams(
      registry,
      { workspace: { id: 1 } },
      { id: 42 },
      { ownership_type: 'restricted' }
    )
    expect(result).toEqual({
      page: 'restricted_view',
      params: { restricted_view_id: 7, table_id: 42 },
      spaceName: 'table-42',
      focusEnabled: false,
    })
  })

  test('returns focusEnabled true when no view provided', () => {
    const registry = mockRegistry(mockOwnershipType())
    const result = resolvePresencePageParams(
      registry,
      { workspace: { id: 1 } },
      { id: 10 },
      null
    )
    expect(result).toEqual({
      page: 'table',
      params: { table_id: 10 },
      spaceName: 'table-10',
      focusEnabled: true,
    })
  })

  test('spaceName always derived from table id regardless of page type', () => {
    const ot = mockOwnershipType({
      supportsPresenceFocus: false,
      page: 'restricted_view',
      params: { restricted_view_id: 99, table_id: 55 },
    })
    const registry = mockRegistry(ot)
    const result = resolvePresencePageParams(
      registry,
      { workspace: { id: 1 } },
      { id: 55 },
      { ownership_type: 'restricted' }
    )
    expect(result.spaceName).toBe('table-55')
  })
})

describe('createPresenceFocusSender', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('emitCellFocus sends cell focus payload after debounce', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(10, 20)
    expect(rt.sendFocus).not.toHaveBeenCalled()
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledWith(
      'table',
      { table_id: 1 },
      {
        type: 'cell',
        row_id: 10,
        field_id: 20,
        editing: false,
      }
    )
  })

  test('emitCellFocus sends editing transition immediately', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(10, 20, true)
    expect(rt.sendFocus).toHaveBeenCalledWith(
      'table',
      { table_id: 1 },
      {
        type: 'cell',
        row_id: 10,
        field_id: 20,
        editing: true,
      }
    )
  })

  test('emitRowFocus sends row focus payload after debounce', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitRowFocus(5)
    expect(rt.sendFocus).not.toHaveBeenCalled()
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledWith(
      'table',
      { table_id: 1 },
      {
        type: 'row',
        row_id: 5,
        editing: false,
      }
    )
  })

  test('clearFocus sends null focus immediately', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.clearFocus()
    expect(rt.sendFocus).toHaveBeenCalledWith('table', { table_id: 1 }, null)
  })

  // -- debounce behavior --

  test('rapid navigation debounces to last call only', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(1, 1)
    sender.emitCellFocus(2, 1)
    sender.emitCellFocus(3, 1)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledOnce()
    expect(rt.sendFocus).toHaveBeenCalledWith(
      'table',
      { table_id: 1 },
      { type: 'cell', row_id: 3, field_id: 1, editing: false }
    )
  })

  test('editing transition cancels pending debounce and sends immediately', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(1, 1)
    expect(rt.sendFocus).not.toHaveBeenCalled()
    sender.emitCellFocus(1, 1, true)
    expect(rt.sendFocus).toHaveBeenCalledOnce()
    expect(rt.sendFocus).toHaveBeenCalledWith(
      'table',
      { table_id: 1 },
      { type: 'cell', row_id: 1, field_id: 1, editing: true }
    )
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledOnce()
  })

  test('clearFocus cancels pending debounce', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(1, 1)
    sender.clearFocus()
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledOnce()
    expect(rt.sendFocus).toHaveBeenCalledWith('table', { table_id: 1 }, null)
  })

  test('destroy cancels pending debounce', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(1, 1)
    sender.destroy()
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  // -- hasOtherMembers gating --

  test('skips send when hasOtherMembers returns false', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => false }
    )
    sender.emitCellFocus(10, 20)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  test('sends when hasOtherMembers returns true', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => true }
    )
    sender.emitCellFocus(10, 20)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledOnce()
  })

  test('sends when no hasOtherMembers option provided', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(10, 20)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledOnce()
  })

  test('clearFocus also gated by hasOtherMembers', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => false }
    )
    sender.clearFocus()
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  // -- reemitLastFocus --

  test('reemitLastFocus sends cached focus regardless of hasOtherMembers', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => false }
    )
    sender.emitCellFocus(10, 20)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).not.toHaveBeenCalled()

    sender.reemitLastFocus()
    expect(rt.sendFocus).toHaveBeenCalledWith(
      'table',
      { table_id: 1 },
      {
        type: 'cell',
        row_id: 10,
        field_id: 20,
        editing: false,
      }
    )
  })

  test('reemitLastFocus does nothing when no focus was ever emitted', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.reemitLastFocus()
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  test('reemitLastFocus sends latest focus after multiple calls', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => false }
    )
    sender.emitCellFocus(1, 2)
    sender.emitCellFocus(3, 4, true)
    sender.reemitLastFocus()
    expect(rt.sendFocus).toHaveBeenCalledWith(
      'table',
      { table_id: 1 },
      {
        type: 'cell',
        row_id: 3,
        field_id: 4,
        editing: true,
      }
    )
  })

  test('reemitLastFocus after clearFocus does nothing', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => false }
    )
    sender.emitCellFocus(1, 2)
    sender.clearFocus()
    sender.reemitLastFocus()
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  test('hasOtherMembers checked dynamically on each call', () => {
    const rt = mockRealtime()
    let members = false
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => members }
    )

    sender.emitCellFocus(1, 2)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).not.toHaveBeenCalled()

    members = true
    sender.emitCellFocus(3, 4)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledOnce()
  })
})
