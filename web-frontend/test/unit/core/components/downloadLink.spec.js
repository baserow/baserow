import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import DownloadLink from '@baserow/modules/core/components/DownloadLink'

describe('DownloadLink', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.unstubAllGlobals()
    await testApp.afterEach()
  })

  test('shows an error when the file cannot be fetched', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 404 })
    )
    const wrapper = await testApp.mount(DownloadLink, {
      props: {
        url: 'http://localhost:8000/media/file.zip',
        filename: 'file.zip',
        loadingClass: 'loading',
      },
      global: { mocks: { $config: { public: { downloadFileViaXhr: '1' } } } },
    })

    await wrapper.find('a').trigger('click')
    await flushPromises()

    expect(
      testApp.store.state.toast.items.map(({ type, title }) => [type, title])
    ).toStrictEqual([['error', 'clientHandler.notCompletedTitle']])
  })
})
