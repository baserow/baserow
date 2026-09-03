import { registerRealtimeEvents } from '@baserow/modules/database/realtime'

const getHandlers = () => {
  const handlers = {}
  registerRealtimeEvents({
    registerEvent: (name, handler) => {
      handlers[name] = handler
    },
  })
  return handlers
}

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
