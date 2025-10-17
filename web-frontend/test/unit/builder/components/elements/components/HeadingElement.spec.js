import { TestApp } from '@baserow/test/helpers/testApp'
import HeadingElement from '@baserow/modules/builder/components/elements/components/HeadingElement.vue'

describe('HeadingElement', () => {
  let testApp = null
  let store = null

  beforeAll(() => {
    testApp = new TestApp()
    store = testApp.store
    store.$registry.registerNamespace('element')
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = ({ props = {}, slots = {}, provide = {} }) => {
    return testApp.mount(HeadingElement, {
      propsData: props,
      slots,
      provide,
    })
  }

  test('Default HeadingElement component', async () => {
    const builder = { id: 1, theme: { primary_color: '#ccc' } }
    const page = {}
    const workspace = {}
    const element = { level: 2, value: { formula: '' }, styles: {} }
    const mode = 'public'

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        mode,
        currentPage: page,
        elementPage: page,
        applicationContext: { builder, page, mode },
        element,
        workspace,
      },
    })
    expect(wrapper.element).toMatchSnapshot()
  })

  test('Default HeadingElement component v2', async () => {
    const builder = { id: 1, theme: { primary_color: '#ccc' } }
    const page = {}
    const workspace = {}
    const element = { level: 3, value: { formula: '"hello"' }, styles: {} }
    const mode = 'public'

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        mode,
        currentPage: page,
        elementPage: page,
        applicationContext: { builder, page, mode },
        element,
        workspace,
      },
    })
    expect(wrapper.element).toMatchSnapshot()
  })
})
