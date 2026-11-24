import { beforeEach, describe, expect, test, vi } from 'vitest'

async function loadPage() {
  vi.resetModules()
  return await import('@baserow_enterprise/utils/assistantTabStorage')
}

describe('Kuma tab id', () => {
  beforeEach(() => sessionStorage.clear())

  test('a reload keeps the id', async () => {
    const tabId = (await loadPage()).getTabId()
    window.dispatchEvent(new Event('pagehide'))
    expect((await loadPage()).getTabId()).toBe(tabId)
  })

  test('a page starting from the storage of a live tab gets its own id', async () => {
    const tabId = (await loadPage()).getTabId()
    expect((await loadPage()).getTabId()).not.toBe(tabId)
  })

  test('a tab back from the back/forward cache keeps its id to itself', async () => {
    const { getTabId } = await loadPage()
    const tabId = getTabId()
    window.dispatchEvent(new Event('pagehide'))
    window.dispatchEvent(new Event('pageshow'))
    expect(getTabId()).toBe(tabId)
    expect((await loadPage()).getTabId()).not.toBe(tabId)
  })
})

describe('Kuma onboarding run', () => {
  beforeEach(() => sessionStorage.clear())

  test('a reload keeps the run', async () => {
    const page = await loadPage()
    page.setOnboardingRunId('run-1')
    window.dispatchEvent(new Event('pagehide'))
    expect((await loadPage()).getOnboardingRunId()).toBe('run-1')
  })

  test('a page starting from the storage of a live tab has no run', async () => {
    const page = await loadPage()
    page.setOnboardingRunId('run-1')
    expect((await loadPage()).getOnboardingRunId()).toBeNull()
  })

  test('a run whose table was opened is gone after a reload', async () => {
    const page = await loadPage()
    page.setOnboardingRunId('run-1')
    page.setOnboardingRunId(null)
    window.dispatchEvent(new Event('pagehide'))
    expect((await loadPage()).getOnboardingRunId()).toBeNull()
  })
})
