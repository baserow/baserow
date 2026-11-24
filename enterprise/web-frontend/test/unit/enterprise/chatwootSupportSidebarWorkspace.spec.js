import { mountSuspended } from '@nuxt/test-utils/runtime'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import ChatwootSupportSidebarWorkspace from '@baserow_enterprise/components/ChatwootSupportSidebarWorkspace'

describe('Direct support', () => {
  let wrapper
  let scripts
  let run
  let dispatch

  beforeEach(async () => {
    scripts = []
    run = vi.fn()
    dispatch = vi.fn()
    vi.stubGlobal('$chatwoot', undefined)
    vi.stubGlobal('chatwootSDK', { run })
    vi.stubGlobal('chatwootSettings', undefined)

    const append = document.head.append.bind(document.head)
    vi.spyOn(document.head, 'append').mockImplementation((...nodes) => {
      for (const node of nodes) {
        if (
          node instanceof HTMLScriptElement &&
          node.src === 'https://support.baserow.io/packs/js/sdk.js'
        ) {
          scripts.push(node)
        } else {
          append(node)
        }
      }
    })

    wrapper = await mountSupport(1)
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  function mountSupport(workspaceId) {
    return mountSuspended(ChatwootSupportSidebarWorkspace, {
      props: { workspace: { id: workspaceId } },
      global: {
        stubs: { PaidFeaturesModal: true },
        mocks: {
          $hasFeature: () => true,
          $i18n: { locale: 'en' },
          $store: {
            dispatch,
            getters: {
              'auth/getUserObject': { id: 2, username: 'user@example.com' },
            },
          },
          $t: (key) => key,
        },
      },
    })
  }

  function mockWidget() {
    return {
      hasLoaded: false,
      setLocale: vi.fn(),
      setUser: vi.fn(),
      setCustomAttributes: vi.fn(),
      toggle: vi.fn(),
    }
  }

  test('allows retry after the SDK script fails', async () => {
    const button = wrapper.get('button')
    await button.trigger('click')
    expect(button.element.disabled).toBe(true)
    await button.trigger('click')
    expect(scripts).toHaveLength(1)

    scripts[0].dispatchEvent(new Event('error'))
    await nextTick()
    expect(button.element.disabled).toBe(false)
    expect(dispatch).toHaveBeenCalledExactlyOnceWith('toast/error', {
      title: 'chatwootSupportSidebarWorkspace.loadError',
    })
    scripts[0].dispatchEvent(new Event('load'))

    await button.trigger('click')
    const widget = mockWidget()
    run.mockImplementationOnce(() => {
      window.$chatwoot = widget
    })
    scripts[1].dispatchEvent(new Event('load'))
    widget.hasLoaded = true
    window.dispatchEvent(new Event('chatwoot:ready'))
    window.dispatchEvent(new Event('chatwoot:ready'))
    await nextTick()

    expect(run).toHaveBeenCalledOnce()
    expect(widget.toggle).toHaveBeenCalledExactlyOnceWith('open')
    expect(button.element.disabled).toBe(false)
  })

  test('retries an unready widget without running the SDK again', async () => {
    const button = wrapper.get('button')
    await button.trigger('click')
    const widget = mockWidget()
    run.mockImplementationOnce(() => {
      window.$chatwoot = widget
    })
    scripts[0].dispatchEvent(new Event('load'))
    await vi.advanceTimersByTimeAsync(10_000)

    expect(dispatch).toHaveBeenCalledExactlyOnceWith('toast/error', {
      title: 'chatwootSupportSidebarWorkspace.loadError',
    })
    expect(button.element.disabled).toBe(false)

    const iframe = document.createElement('iframe')
    iframe.src = 'about:blank'
    const setAttribute = vi.spyOn(iframe, 'setAttribute')
    const getElementById = document.getElementById.bind(document)
    vi.spyOn(document, 'getElementById').mockImplementation((id) =>
      id === 'chatwoot_live_chat_widget' ? iframe : getElementById(id)
    )

    await button.trigger('click')
    expect(setAttribute).toHaveBeenCalledExactlyOnceWith('src', 'about:blank')
    expect(scripts).toHaveLength(1)
    expect(run).toHaveBeenCalledOnce()
    widget.hasLoaded = true
    window.dispatchEvent(new Event('chatwoot:ready'))
    await nextTick()

    expect(widget.toggle).toHaveBeenCalledExactlyOnceWith('open')
    expect(button.element.disabled).toBe(false)
  })

  test('drops pending work on unmount and opens for the next workspace on demand', async () => {
    await wrapper.get('button').trigger('click')
    wrapper.unmount()
    wrapper = undefined
    const widget = mockWidget()
    widget.hasLoaded = true
    window.$chatwoot = widget
    scripts[0].dispatchEvent(new Event('load'))
    window.dispatchEvent(new Event('chatwoot:ready'))
    await vi.advanceTimersByTimeAsync(10_000)

    expect(run).not.toHaveBeenCalled()
    expect(widget.toggle).not.toHaveBeenCalled()
    expect(dispatch).not.toHaveBeenCalled()

    vi.useRealTimers()
    wrapper = await mountSupport(3)
    await wrapper.get('button').trigger('click')
    expect(scripts).toHaveLength(1)
    expect(widget.toggle).toHaveBeenCalledExactlyOnceWith('open')
    expect(widget.setCustomAttributes).toHaveBeenCalledWith({
      workspaceId: 3,
      userId: 2,
      domain: window.location.hostname,
    })
  })
})
