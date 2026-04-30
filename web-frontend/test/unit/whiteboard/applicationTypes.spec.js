import { describe, expect, test, vi } from 'vitest'
import { WhiteboardApplicationType } from '@baserow/modules/whiteboard/applicationTypes'
import { DEVELOPMENT_STAGES } from '@baserow/modules/core/constants'

const buildApp = () => ({
  $i18n: {
    t: (key) => key,
  },
  hooks: {
    hookOnce: (event, callback) => {
      callback()
    },
  },
})

describe('WhiteboardApplicationType', () => {
  test('exposes the expected static type', () => {
    expect(WhiteboardApplicationType.getType()).toBe('whiteboard')
  })

  test('exposes i18n-driven names', () => {
    const type = new WhiteboardApplicationType({ app: buildApp() })
    expect(type.getName()).toBe('applicationType.whiteboard')
    expect(type.getNamePlural()).toBe('applicationType.whiteboards')
    expect(type.getDescription()).toBe('applicationType.whiteboardDesc')
    expect(type.getDefaultName()).toBe('applicationType.whiteboardDefaultName')
  })

  test('uses the iconoir-frame icon', () => {
    const type = new WhiteboardApplicationType({ app: buildApp() })
    expect(type.getIconClass()).toBe('iconoir-frame')
  })

  test('does not support trash and lives in alpha', () => {
    const type = new WhiteboardApplicationType({ app: buildApp() })
    expect(type.supportsTrash()).toBe(false)
    expect(type.developmentStage).toBe(DEVELOPMENT_STAGES.ALPHA)
    expect(type.getOrder()).toBe(85)
  })

  test('select navigates to the whiteboard route with the application id', async () => {
    const type = new WhiteboardApplicationType({ app: buildApp() })
    const $router = { push: vi.fn().mockResolvedValue() }
    await type.select({ id: 42 }, { $router })
    expect($router.push).toHaveBeenCalledWith({
      name: 'whiteboard-application',
      params: { whiteboardId: 42 },
    })
  })

  test('delete navigates to the dashboard list', () => {
    const type = new WhiteboardApplicationType({ app: buildApp() })
    const $router = { push: vi.fn() }
    type.delete({ id: 42 }, { $router })
    expect($router.push).toHaveBeenCalledWith({ name: 'dashboard' })
  })
})
