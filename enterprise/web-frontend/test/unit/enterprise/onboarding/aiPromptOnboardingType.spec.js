import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { AIPromptOnboardingType } from '@baserow_enterprise/onboardingTypes'
import {
  getStoredOnboardingRunId,
  getStoredPanelOpen,
} from '@baserow_enterprise/utils/assistantTabStorage'

const workspace = { id: 3 }
const data = { ai_prompt: { prompt: 'A CRM', industry: 'Sales', team: 'Ops' } }

function onboardingStep({
  start = { outcome: 'accepted', runId: 'run-1' },
} = {}) {
  const app = {
    $i18n: { t: (key) => key },
    $store: {
      dispatch: vi.fn(async (action) =>
        action === 'assistant/startRun' ? start : undefined
      ),
    },
    $bus: { $emit: vi.fn() },
    hooks: { hookOnce: (name, callback) => callback() },
  }
  return { app, step: new AIPromptOnboardingType({ app }) }
}

const complete = (step) =>
  step.complete(data, { database: { workspace } }, vi.fn())

describe('AIPromptOnboardingType', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  test('hands off to the workspace and opens the panel once Kuma accepted the message', async () => {
    const { app, step } = onboardingStep()

    const response = await complete(step)
    const route = step.getCompletedRoute(data, { ai_prompt: response })
    await flushPromises()

    expect(response).toEqual({ workspace, runId: 'run-1' })
    expect(getStoredPanelOpen()).toBe(true)
    expect(getStoredOnboardingRunId()).toBe('run-1')
    expect(route).toEqual({ name: 'workspace', params: { workspaceId: 3 } })
    expect(app.$bus.$emit).toHaveBeenCalledWith('toggle-right-sidebar', true)
  })

  test('fails when Kuma did not accept the message', async () => {
    const { step } = onboardingStep({
      start: { outcome: 'failed', runId: null },
    })

    await expect(complete(step)).rejects.toThrow()
    expect(getStoredOnboardingRunId()).toBe(null)
  })
})
