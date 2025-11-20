import ButtonElement from '@baserow/modules/builder/components/elements/components/ButtonElement'
import { TestApp } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'

describe('Test MyComponent', () => {
  let testApp = null
  let mockServer = null
  let store = null

  beforeAll(() => {
    testApp = new TestApp()
    store = testApp.store // Give access to the store
    mockServer = testApp.mockServer // Give access to the fake API
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = ({
    props = {},
    slots = {},
    provide = {},
    listeners = {},
  }) => {
    return testApp.mount(ButtonElement, {
      propsData: props,
      slots,
      provide,
      listeners,
    })
  }

  test('Default component', async () => {
    const page = {
      id: 1,
      workflowActions: [],
      dataSources: [],
      elements: [],
    }
    const sharedPage = {
      id: 2,
      workflowAction: [],
      dataSources: [],
      elements: [],
      shared: true,
    }
    const builder = {
      id: 1,
      theme: { primary_color: '#ccc' },
      pages: [sharedPage, page],
    }
    const workspace = {}
    const mode = 'public'
    const element = {
      id: 1,
      type: 'button',
    }
    store.dispatch('element/forceCreate', { page, element })

    await flushPromises()

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        currentPage: page,
        elementPage: page,
        mode,
        applicationContext: { builder, page, mode },
        element,
        workspace,
      },
    })

    // Check the result
    expect(wrapper.element).toMatchSnapshot()
  })
})
