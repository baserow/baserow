import { describe, expect, test, vi } from 'vitest'
import { downloadJson } from '@baserow_enterprise/utils/download'

describe('downloadJson', () => {
  test('offers the pretty-printed JSON as a file download', () => {
    const clicks = []
    global.URL.createObjectURL = vi.fn(() => 'blob:manifest')
    global.URL.revokeObjectURL = vi.fn()
    const originalCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      const element = originalCreate(tag)
      element.click = () =>
        clicks.push({ href: element.href, name: element.download })
      return element
    })

    downloadJson(
      { display_information: { name: 'Bot' } },
      'bot-slack-manifest.json'
    )

    expect(clicks).toEqual([
      { href: 'blob:manifest', name: 'bot-slack-manifest.json' },
    ])
    const blob = global.URL.createObjectURL.mock.calls[0][0]
    expect(blob.type).toBe('application/json')
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:manifest')
  })
})
