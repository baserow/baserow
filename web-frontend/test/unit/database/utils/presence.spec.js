import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest'

import {
  ANONYMOUS_FOCUS_ENABLED,
  createPresenceFocusSender,
  getPresenceVisibleUsers,
  isUserPresenceEnabled,
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

describe('isUserPresenceEnabled', () => {
  function mockVm({ visibleUsers = '3' } = {}) {
    return {
      $config: { public: { baserowPresenceVisibleUsers: visibleUsers } },
    }
  }

  test('enabled when visible users > 0', () => {
    expect(isUserPresenceEnabled(mockVm())).toBe(true)
  })

  test('disabled when visible users is 0', () => {
    expect(isUserPresenceEnabled(mockVm({ visibleUsers: '0' }))).toBe(false)
  })

  test('disabled when visible users is missing', () => {
    expect(isUserPresenceEnabled({ $config: { public: {} } })).toBe(false)
  })
})

describe('getPresenceVisibleUsers', () => {
  test('parses integer from config string', () => {
    const vm = { $config: { public: { baserowPresenceVisibleUsers: '5' } } }
    expect(getPresenceVisibleUsers(vm)).toBe(5)
  })

  test('returns 0 for missing config', () => {
    expect(getPresenceVisibleUsers({ $config: { public: {} } })).toBe(0)
  })

  test('returns 0 for non-numeric string', () => {
    const vm = { $config: { public: { baserowPresenceVisibleUsers: 'abc' } } }
    expect(getPresenceVisibleUsers(vm)).toBe(0)
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

  test('returns focusEnabled matching ANONYMOUS_FOCUS_ENABLED for public view', () => {
    const result = resolvePresencePageParams(null, null, null, null, {
      isPublicView: true,
      slug: 'abc',
      token: 'tok',
    })
    expect(result).toEqual({
      page: 'view',
      params: { slug: 'abc', token: 'tok' },
      spaceName: null,
      focusEnabled: ANONYMOUS_FOCUS_ENABLED,
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

  test('clearFocus sends null immediately after a transmitted focus', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(10, 20, true)
    sender.clearFocus()
    expect(rt.sendFocus).toHaveBeenLastCalledWith(
      'table',
      { table_id: 1 },
      null
    )
  })

  test('clearFocus transmits nothing when nothing was ever transmitted', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.clearFocus()
    expect(rt.sendFocus).not.toHaveBeenCalled()
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

  test('clearFocus cancels pending debounce and transmits nothing when the debounce never fired', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(1, 1)
    sender.clearFocus()
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  test('clearFocus transmits null after a debounced focus fired', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(rt, 'table', { table_id: 1 })
    sender.emitCellFocus(1, 1)
    vi.advanceTimersByTime(150)
    sender.clearFocus()
    expect(rt.sendFocus).toHaveBeenCalledTimes(2)
    expect(rt.sendFocus).toHaveBeenLastCalledWith(
      'table',
      { table_id: 1 },
      null
    )
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

  test('clearFocus bypasses the gate once a focus was transmitted', () => {
    const rt = mockRealtime()
    let members = true
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => members }
    )
    sender.emitCellFocus(1, 1)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).toHaveBeenCalledOnce()

    members = false
    sender.clearFocus()
    expect(rt.sendFocus).toHaveBeenCalledTimes(2)
    expect(rt.sendFocus).toHaveBeenLastCalledWith(
      'table',
      { table_id: 1 },
      null
    )
  })

  test('gated clearFocus transmits nothing when nothing was ever transmitted', () => {
    const rt = mockRealtime()
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => false }
    )
    sender.emitCellFocus(1, 1)
    vi.advanceTimersByTime(150)
    sender.clearFocus()
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  test('gated sendDebounced cancels an armed timer', () => {
    const rt = mockRealtime()
    let members = true
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => members }
    )
    sender.emitCellFocus(1, 1)
    members = false
    sender.emitCellFocus(2, 2)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  test('gated immediate send cancels an armed timer', () => {
    const rt = mockRealtime()
    let members = true
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => members }
    )
    sender.emitCellFocus(1, 1)
    members = false
    sender.emitCellFocus(1, 1, true)
    vi.advanceTimersByTime(150)
    expect(rt.sendFocus).not.toHaveBeenCalled()
  })

  // -- reemitLastFocus --

  test('reemitLastFocus respects the hasOtherMembers gate', () => {
    const rt = mockRealtime()
    let members = false
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => members }
    )
    sender.emitCellFocus(10, 20)
    vi.advanceTimersByTime(150)
    sender.reemitLastFocus()
    expect(rt.sendFocus).not.toHaveBeenCalled()

    members = true
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

  test('reemitLastFocus marks the focus as transmitted so a later clear goes out', () => {
    const rt = mockRealtime()
    let members = false
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => members }
    )
    sender.emitCellFocus(10, 20)
    vi.advanceTimersByTime(150)

    members = true
    sender.reemitLastFocus()
    members = false
    sender.clearFocus()
    expect(rt.sendFocus).toHaveBeenLastCalledWith(
      'table',
      { table_id: 1 },
      null
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
    let members = false
    const sender = createPresenceFocusSender(
      rt,
      'table',
      { table_id: 1 },
      { hasOtherMembers: () => members }
    )
    sender.emitCellFocus(1, 2)
    sender.emitCellFocus(3, 4, true)
    members = true
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
