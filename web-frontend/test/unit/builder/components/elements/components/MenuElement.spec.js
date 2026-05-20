import { mountSuspended } from '@nuxt/test-utils/runtime'
import MenuElement from '@baserow/modules/builder/components/elements/components/MenuElement.vue'
import {
  HORIZONTAL_ALIGNMENTS,
  ORIENTATIONS,
} from '@baserow/modules/builder/enums'

describe('MenuElement', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = useNuxtApp()
    store = testApp.$store
    store.dispatch('page/setDeviceTypeSelected', 'desktop')
  })

  const page = {
    id: 1,
    path: '/',
    shared: false,
    order: 1,
    elements: [],
  }
  const builder = {
    id: 1,
    theme: { primary_color: '#ccc' },
    pages: [page],
  }
  const workspace = {}
  const mode = 'editing'

  const createMenuItem = (overrides = {}) => ({
    id: 1,
    uid: 'menu-item-1',
    type: 'link',
    name: 'Page',
    variant: 'link',
    navigation_type: 'custom',
    navigate_to_url: { formula: '"https://baserow.io"' },
    parent_menu_item: null,
    children: [],
    ...overrides,
  })

  const createElement = (overrides = {}) => ({
    id: 42,
    type: 'menu',
    page_id: page.id,
    orientation: ORIENTATIONS.HORIZONTAL,
    alignment: HORIZONTAL_ALIGNMENTS.LEFT,
    variant: {
      desktop: 'expanded',
      tablet: 'compact',
      smartphone: 'compact',
    },
    styles: {},
    menu_items: [createMenuItem()],
    ...overrides,
  })

  const mountComponent = async ({ element, deviceType = 'desktop' }) => {
    await store.dispatch('page/setDeviceTypeSelected', deviceType)
    return mountSuspended(MenuElement, {
      props: { element },
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext: { builder, page, mode },
          element,
          workspace,
        },
        stubs: {
          'client-only': { template: '<div><slot /></div>' },
        },
      },
    })
  }

  const openCompactMenu = async (wrapper) => {
    await wrapper.find('.menu-element__burger-menu-icon').trigger('click')
  }

  test('shows the compact burger control for the selected desktop device', async () => {
    const wrapper = await mountComponent({
      element: createElement({
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
      }),
    })

    expect(wrapper.find('.menu-element__burger-menu').exists()).toBe(true)
    expect(wrapper.find('.menu-element__container--burger').exists()).toBe(
      false
    )
    expect(wrapper.find('.menu-element__menu-item-link').exists()).toBe(false)
  })

  test('opens compact menu items when the burger control is clicked', async () => {
    const wrapper = await mountComponent({
      element: createElement({
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
      }),
    })

    await openCompactMenu(wrapper)

    expect(wrapper.find('.menu-element__container--burger').exists()).toBe(true)
    expect(
      wrapper.find('.menu-element__burger-menu .iconoir-menu').exists()
    ).toBe(true)
    expect(
      wrapper
        .find('.menu-element__container--burger .menu-element__burger-menu')
        .exists()
    ).toBe(false)
    expect(
      wrapper
        .find(
          '.menu-element__container--burger .menu-element__burger-menu-close'
        )
        .exists()
    ).toBe(true)
    expect(wrapper.find('.menu-element__burger-menu').exists()).toBe(true)
    expect(wrapper.find('.menu-element__menu-item-link').exists()).toBe(true)
    expect(wrapper.text()).toContain('Page')
  })

  test('keeps default alignment inside the compact panel', async () => {
    const wrapper = await mountComponent({
      element: createElement({
        alignment: HORIZONTAL_ALIGNMENTS.RIGHT,
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
      }),
    })

    await openCompactMenu(wrapper)

    expect(
      wrapper.find('.menu-element__container--burger').attributes('style')
    ).toContain('--alignment: flex-start')
  })

  test('closes compact menu from the close control inside the panel', async () => {
    const wrapper = await mountComponent({
      element: createElement({
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
      }),
    })

    await openCompactMenu(wrapper)
    await wrapper.find('.menu-element__burger-menu-close').trigger('click')

    expect(wrapper.find('.menu-element__container--burger').exists()).toBe(
      false
    )
    expect(wrapper.find('.menu-element__burger-menu').exists()).toBe(true)
    expect(
      wrapper.find('.menu-element__burger-menu .iconoir-menu').exists()
    ).toBe(true)
  })

  test('closes compact menu when clicking outside the panel', async () => {
    const wrapper = await mountComponent({
      element: createElement({
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
      }),
    })

    await openCompactMenu(wrapper)
    await wrapper.vm.$nextTick()

    document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.menu-element__container--burger').exists()).toBe(
      false
    )
  })

  test('keeps the expanded menu when desktop variant is expanded', async () => {
    const wrapper = await mountComponent({
      element: createElement(),
    })

    expect(wrapper.find('.menu-element__burger-menu').exists()).toBe(false)
    expect(wrapper.find('.menu-element__container--horizontal').exists()).toBe(
      true
    )
    expect(wrapper.find('.menu-element__menu-item-link').exists()).toBe(true)
  })

  test('renders sub links inline in compact mode', async () => {
    const parentItem = createMenuItem({
      children: [
        createMenuItem({
          id: 2,
          uid: 'menu-item-2',
          name: 'Child page',
          parent_menu_item: 1,
        }),
      ],
    })
    const wrapper = await mountComponent({
      element: createElement({
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
        menu_items: [parentItem],
      }),
    })

    await openCompactMenu(wrapper)
    await wrapper
      .find('.menu-element__menu-item-with-children')
      .trigger('click')

    expect(wrapper.find('.menu-element__sub-link').exists()).toBe(true)
    expect(wrapper.text()).toContain('Child page')
  })

  test('marks spacer items so they push following items down in compact mode', async () => {
    const wrapper = await mountComponent({
      element: createElement({
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
        menu_items: [
          createMenuItem({ id: 1, uid: 'menu-item-1', name: 'Top page' }),
          createMenuItem({ id: 2, uid: 'menu-item-2', type: 'spacer' }),
          createMenuItem({ id: 3, uid: 'menu-item-3', name: 'Bottom page' }),
        ],
      }),
    })

    await openCompactMenu(wrapper)

    const spacer = wrapper.find('.menu-element__menu-item-spacer')
    expect(spacer.exists()).toBe(true)
  })
})
