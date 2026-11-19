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
