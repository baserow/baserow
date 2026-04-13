import { WhiteboardApplicationType } from '@baserow/modules/whiteboard/applicationTypes'
import { expect, test, vi } from 'vitest'

describe('WhiteboardApplicationType', () => {
  let appType

  beforeEach(() => {
    const app = {
      $i18n: {
        t: (key) => key,
      },
    }
    appType = new WhiteboardApplicationType({ app })
  })

  test('getType returns whiteboard', () => {
    expect(WhiteboardApplicationType.getType()).toBe('whiteboard')
  })

  test('getIconClass returns iconoir-frame', () => {
    expect(appType.getIconClass()).toBe('iconoir-frame')
  })

  test('getName returns translation key', () => {
    expect(appType.getName()).toBe('applicationType.whiteboard')
  })

  test('getNamePlural returns translation key', () => {
    expect(appType.getNamePlural()).toBe('applicationType.whiteboards')
  })

  test('getDescription returns translation key', () => {
    expect(appType.getDescription()).toBe('applicationType.whiteboardDesc')
  })

  test('supportsTrash returns false', () => {
    expect(appType.supportsTrash()).toBe(false)
  })

  test('getOrder returns 85', () => {
    expect(appType.getOrder()).toBe(85)
  })

  test('select navigates to whiteboard-application route', async () => {
    const push = vi.fn().mockResolvedValue(undefined)
    const $router = { push }

    // Mock pageFinished by making it a no-op
    await appType.select({ id: 42 }, { $router }).catch(() => {})

    expect(push).toHaveBeenCalledWith({
      name: 'whiteboard-application',
      params: { whiteboardId: 42 },
    })
  })
})
