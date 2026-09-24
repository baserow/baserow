import { describe, expect, test, vi } from 'vitest'
import buttonField from '@baserow/modules/database/mixins/buttonField'

function context({ executeResults, posthog }) {
  const execute = vi.fn()
  executeResults.forEach((result) => execute.mockResolvedValueOnce(result))
  return {
    field: { id: 7 },
    allFieldsInTable: [{ id: 1 }],
    $registry: { get: () => ({ execute }) },
    $posthog: posthog,
    resultsBefore: buttonField.methods.resultsBefore,
    execute,
  }
}

const actions = [
  { id: 1, type: 'open_url', position: 1 },
  { id: 2, type: 'open_url', position: 2 },
]

describe('buttonField runClientActions', () => {
  test('captures whether each client action ran', async () => {
    const posthog = { capture: vi.fn() }
    const ctx = context({ executeResults: [undefined, false], posthog })

    await buttonField.methods.runClientActions.call(ctx, actions, {})

    expect(posthog.capture.mock.calls).toEqual([
      [
        'button_field_client_action',
        { field_id: 7, workflow_action_type: 'open_url', ran: true },
      ],
      [
        'button_field_client_action',
        { field_id: 7, workflow_action_type: 'open_url', ran: false },
      ],
    ])
  })

  test('runs the actions when PostHog is not configured', async () => {
    const ctx = context({ executeResults: [true, true], posthog: undefined })

    await buttonField.methods.runClientActions.call(ctx, actions, {})

    expect(ctx.execute).toHaveBeenCalledTimes(2)
  })

  test('a failing capture does not stop the next action', async () => {
    const posthog = {
      capture: vi.fn(() => {
        throw new Error('blocked')
      }),
    }
    const ctx = context({ executeResults: [true, true], posthog })

    await buttonField.methods.runClientActions.call(ctx, actions, {})

    expect(ctx.execute).toHaveBeenCalledTimes(2)
  })
})
