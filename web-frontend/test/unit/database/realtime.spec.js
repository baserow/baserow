import { registerRealtimeEvents } from '@baserow/modules/database/realtime'
import { ViewType } from '@baserow/modules/database/viewTypes'
import flushPromises from 'flush-promises'

const getHandlers = () => {
  const handlers = {}
  registerRealtimeEvents({
    registerEvent: (name, handler) => {
      handlers[name] = handler
    },
  })
  return handlers
}

describe('database realtime row update batches', () => {
  test('keeps non-grid view updates sequential within a frame', async () => {
    const handlers = getHandlers()
    const viewType = Object.create(ViewType.prototype)
    let finishFirstUpdate
    viewType.rowUpdated = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishFirstUpdate = resolve
          })
      )
      .mockResolvedValue()
    const store = {
      getters: { 'field/getAll': [] },
      dispatch: vi.fn().mockResolvedValue(),
    }
    const context = {
      store,
      app: { $registry: { getAll: () => ({ view: viewType }) } },
    }
    const updating = handlers.rows_updated(context, {
      table_id: 1,
      rows: [{ id: 10 }, { id: 11 }],
      metadata: {},
      updated_field_ids: [],
    })

    try {
      await flushPromises()
      expect(viewType.rowUpdated).toHaveBeenCalledTimes(1)
      expect(viewType.rowUpdated.mock.calls[0][3]).toEqual({ id: 10 })
      expect(store.dispatch).not.toHaveBeenCalled()
    } finally {
      finishFirstUpdate()
      await updating
    }

    expect(viewType.rowUpdated).toHaveBeenCalledTimes(2)
    expect(viewType.rowUpdated.mock.calls[1][3]).toEqual({ id: 11 })
    expect(store.dispatch).toHaveBeenCalledTimes(2)
  })
})

describe('database realtime AI provider updates', () => {
  test('refreshes cached field errors when model availability changes', async () => {
    const handlers = getHandlers()
    const store = {
      getters: {
        'field/isLoaded': true,
      },
      dispatch: vi.fn().mockResolvedValue(),
    }

    await handlers.ai_provider_updated(
      { store },
      {
        model_availability_updated: true,
      }
    )

    expect(store.dispatch).toHaveBeenCalledWith(
      'field/refreshLoadedFieldErrors',
      { realtimeRecovery: true }
    )
  })

  test('does not refresh field errors for provider metadata changes', async () => {
    const handlers = getHandlers()
    const store = {
      getters: {
        'field/isLoaded': true,
      },
      dispatch: vi.fn().mockResolvedValue(),
    }

    await handlers.ai_provider_updated(
      { store },
      {
        model_availability_updated: false,
      }
    )

    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('uses primary recovery for an oversized availability marker', async () => {
    const handlers = getHandlers()
    const store = {
      getters: {
        'field/isLoaded': true,
      },
      dispatch: vi.fn().mockResolvedValue(),
    }

    await handlers.ai_provider_updated(
      { store },
      {
        model_availability_updated: true,
        requires_refresh: true,
        refresh_workspace_availability: true,
      }
    )

    expect(store.dispatch).toHaveBeenCalledWith(
      'field/refreshLoadedFieldErrors',
      { realtimeRecovery: true }
    )
  })

  test('refreshes cached field errors when workspace AI settings change', async () => {
    const handlers = getHandlers()
    const store = {
      getters: {
        'field/isLoaded': true,
      },
      dispatch: vi.fn().mockResolvedValue(),
    }

    await handlers.group_updated(
      { store },
      {
        updated_fields: ['generative_ai_models_settings'],
      }
    )

    expect(store.dispatch).toHaveBeenCalledWith(
      'field/refreshLoadedFieldErrors',
      { realtimeRecovery: true }
    )
  })

  test('does not refresh field errors when workspace metadata changes', async () => {
    const handlers = getHandlers()
    const store = {
      getters: {
        'field/isLoaded': true,
      },
      dispatch: vi.fn().mockResolvedValue(),
    }

    await handlers.group_updated(
      { store },
      {
        updated_fields: ['name'],
      }
    )

    expect(store.dispatch).not.toHaveBeenCalled()
  })
})

describe('database realtime button field updates', () => {
  test('updates the buttons in place without refreshing the grid', async () => {
    const handlers = getHandlers()
    const store = { dispatch: vi.fn().mockResolvedValue() }
    const app = { $bus: { $emit: vi.fn() } }
    const fields = [
      { id: 1, type: 'button', requires_reconfiguration: true },
      { id: 2, type: 'button', requires_reconfiguration: true },
    ]

    await handlers.button_fields_updated({ store, app }, { fields })

    expect(store.dispatch).toHaveBeenCalledWith('field/forceUpdateFields', {
      fields,
    })
    // A `table-refresh` would refetch every row for a boolean, and throw away
    // what someone is typing in a cell.
    expect(app.$bus.$emit).not.toHaveBeenCalled()
  })
})
