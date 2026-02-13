import HeadingElement from '@baserow/modules/builder/components/elements/components/HeadingElement.vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

describe('HeadingElement', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = useNuxtApp()
    store = testApp.$store
  })

  const mountComponent = ({ props = {}, slots = {}, provide = {} }) => {
    return mountSuspended(HeadingElement, {
      props,
      slots,
      global: { provide },
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
