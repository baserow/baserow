import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import {
  downloadViaXhr,
  triggerDownload,
} from '@baserow/modules/core/utils/download'

const url = 'https://files.example.com/template-revisions/abc.zip'
const filename = 'sales-pipeline.zip'

describe('download', () => {
  let clicked = []

  beforeEach(() => {
    clicked = []
    // Records the clicked anchors, without navigating.
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(
      function () {
        clicked.push(this)
      }
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  test('downloadViaXhr throws on a failed response without saving it', async () => {
    const blob = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 403, blob }))
    )

    await expect(downloadViaXhr(url, filename)).rejects.toThrow('403')

    expect(blob).not.toHaveBeenCalled()
    expect(clicked).toHaveLength(0)
  })

  test.each([
    ['unknown', null, '_blank'],
    ['active', true, '_blank'],
    // The click no longer counts, so a new tab would be blocked.
    ['expired', false, ''],
  ])(
    'triggerDownload with the user activation %s',
    async (_, isActive, target) => {
      if (isActive !== null) {
        vi.stubGlobal(
          'navigator',
          Object.create(navigator, { userActivation: { value: { isActive } } })
        )
      }

      await triggerDownload(url, filename)

      expect(clicked.map((anchor) => anchor.target)).toStrictEqual([target])
    }
  )
})
