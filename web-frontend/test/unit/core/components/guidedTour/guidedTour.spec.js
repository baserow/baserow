import flushPromises from 'flush-promises'
import GuidedTour from '@baserow/modules/core/components/guidedTour/GuidedTour'
import {
  GuidedTourType,
  GuidedTourStep,
} from '@baserow/modules/core/guidedTourTypes'
import { TestApp } from '@baserow/test/helpers/testApp'

class TestGuidedTourStep extends GuidedTourStep {
  constructor(app, content, { showOnReplay = true } = {}) {
    super(app, 'Title', content)
    this._showOnReplay = showOnReplay
  }

  get selectors() {
    return []
  }

  get position() {
    return 'center'
  }

  get showOnReplay() {
    return this._showOnReplay
  }
}

class MainTestGuidedTourType extends GuidedTourType {
  static getType() {
    return 'test_main'
  }

  get steps() {
    return [
      new TestGuidedTourStep(this.app, 'main step 1'),
      new TestGuidedTourStep(this.app, 'main step 2 first time only', {
        showOnReplay: false,
      }),
      new TestGuidedTourStep(this.app, 'main step 3'),
    ]
  }

  get order() {
    return 1
  }

  isActive() {
    return true
  }
}

class FirstTimeOnlyTestGuidedTourType extends GuidedTourType {
  static getType() {
    return 'test_first_time_only'
  }

  get showOnReplay() {
    return false
  }

  get steps() {
    return [new TestGuidedTourStep(this.app, 'first time only tour step')]
  }

  get order() {
    return 2
  }

  isActive() {
    return true
  }
}

describe('GuidedTour component', () => {
  let testApp = null
  let store = null
  const originalResizeObserver = globalThis.ResizeObserver

  beforeAll(() => {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  })

  afterAll(() => {
    globalThis.ResizeObserver = originalResizeObserver
  })

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store

    // Replace the real guided tours with predictable test tours so the assertions
    // don't depend on their steps.
    const registry = testApp.getRegistry()
    Object.keys(registry.getAll('guidedTour')).forEach((type) =>
      registry.unregister('guidedTour', type)
    )
    const context = { app: testApp.getApp() }
    registry.register('guidedTour', new MainTestGuidedTourType(context))
    registry.register(
      'guidedTour',
      new FirstTimeOnlyTestGuidedTourType(context)
    )
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const authenticate = (completedGuidedTours) => {
    store.dispatch('auth/forceSetUserData', {
      user: {
        id: 256,
        completed_guided_tours: completedGuidedTours,
      },
      access_token:
        `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImpvaG5AZXhhb` +
        `XBsZS5jb20iLCJpYXQiOjE2NjAyOTEwODYsImV4cCI6MTY2MDI5NDY4NiwianRpIjo` +
        `iNDZmNzUwZWUtMTJhMS00N2UzLWJiNzQtMDIwYWM4Njg3YWMzIiwidXNlcl9pZCI6M` +
        `iwidXNlcl9wcm9maWxlX2lkIjpbMl0sIm9yaWdfaWF0IjoxNjYwMjkxMDg2fQ.RQ-M` +
        `NQdDR9zTi8CbbQkRrwNsyDa5CldQI83Uid1l9So`,
    })
  }

  const visibleStepContent = (wrapper) =>
    wrapper.find('.guided-tour-step__description').text()

  const clickNext = async (wrapper) => {
    await wrapper.find('.guided-tour-step__foot button').trigger('click')
    await flushPromises()
  }

  test('tours start automatically the first time and save the completed state', async () => {
    authenticate([])
    testApp.mock.onPatch('/user/account/').reply(200, {})

    const wrapper = await testApp.mount(GuidedTour, {})

    expect(wrapper.find('.guided-tour-step').exists()).toBe(true)
    // Automatically started tours cannot be stopped.
    expect(wrapper.find('.guided-tour-step__close').exists()).toBe(false)

    // All steps of both tours are included, in order.
    for (const content of [
      'main step 1',
      'main step 2 first time only',
      'main step 3',
      'first time only tour step',
    ]) {
      expect(visibleStepContent(wrapper)).toBe(content)
      await clickNext(wrapper)
    }

    expect(wrapper.find('.guided-tour-step').exists()).toBe(false)
    expect(testApp.mock.history.patch.length).toBe(1)
    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      completed_guided_tours: ['test_main', 'test_first_time_only'],
    })
  })

  test('completed tours do not start automatically', async () => {
    authenticate(['test_main', 'test_first_time_only'])

    const wrapper = await testApp.mount(GuidedTour, {})

    expect(wrapper.find('.guided-tour-step').exists()).toBe(false)
  })

  test(
    'replaying includes completed tours, skips first time only tours and ' +
      'steps, and does not save',
    async () => {
      authenticate(['test_main', 'test_first_time_only'])

      const wrapper = await testApp.mount(GuidedTour, {})
      await store.dispatch('guidedTour/forceStart')
      await flushPromises()

      expect(wrapper.find('.guided-tour-step').exists()).toBe(true)
      // Manually replayed tours can be stopped.
      expect(wrapper.find('.guided-tour-step__close').exists()).toBe(true)

      // The `test_first_time_only` tour and the second step of the `test_main`
      // tour are excluded because of their `showOnReplay` value.
      for (const content of ['main step 1', 'main step 3']) {
        expect(visibleStepContent(wrapper)).toBe(content)
        await clickNext(wrapper)
      }

      expect(wrapper.find('.guided-tour-step').exists()).toBe(false)
      expect(store.getters['guidedTour/isForced']).toBe(false)
      // Finishing a replayed tour must not persist anything.
      expect(testApp.mock.history.patch.length).toBe(0)
    }
  )

  test('a replayed tour can be stopped and replayed again', async () => {
    authenticate(['test_main', 'test_first_time_only'])

    const wrapper = await testApp.mount(GuidedTour, {})
    await store.dispatch('guidedTour/forceStart')
    await flushPromises()

    await wrapper.find('.guided-tour-step__close').trigger('click')
    await flushPromises()

    expect(wrapper.find('.guided-tour-step').exists()).toBe(false)
    expect(store.getters['guidedTour/isForced']).toBe(false)
    expect(testApp.mock.history.patch.length).toBe(0)

    // Replaying again restarts from the first step.
    await store.dispatch('guidedTour/forceStart')
    await flushPromises()

    expect(wrapper.find('.guided-tour-step').exists()).toBe(true)
    expect(visibleStepContent(wrapper)).toBe('main step 1')
  })
})
