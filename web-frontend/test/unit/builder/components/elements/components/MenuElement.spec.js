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
    _: {
      compactMenuOpen: false,
    },
    styles: {},
    menu_items: [createMenuItem()],
    ...overrides,
  })

  const mountComponent = async ({
    element,
    deviceType = 'desktop',
    componentMode = 'public',
  }) => {
    page.elements = [element]
    await store.dispatch('page/setDeviceTypeSelected', deviceType)
    return mountSuspended(MenuElement, {
      props: { element },
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode: componentMode,
          applicationContext: { builder, page, mode: componentMode },
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
    await wrapper
      .find('.menu-element__compact-menu-trigger-icon')
      .trigger('click')
  }

  test('shows the compact menu trigger for the selected desktop device', async () => {
    const wrapper = await mountComponent({
      element: createElement({
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
      }),
    })

    expect(wrapper.find('.menu-element__compact-menu-trigger').exists()).toBe(
      true
    )
    expect(wrapper.find('.menu-element__container--compact').exists()).toBe(
      false
    )
    expect(wrapper.find('.menu-element__menu-item-link').exists()).toBe(false)
  })

  test('opens compact menu items when the trigger is clicked', async () => {
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

    expect(wrapper.find('.menu-element__container--compact').exists()).toBe(
      true
    )
    expect(
      wrapper.find('.menu-element__compact-menu-trigger .iconoir-menu').exists()
    ).toBe(true)
    expect(
      wrapper
        .find(
          '.menu-element__container--compact .menu-element__compact-menu-trigger'
        )
        .exists()
    ).toBe(false)
    expect(
      wrapper
        .find(
          '.menu-element__container--compact .menu-element__compact-menu-close'
        )
        .exists()
    ).toBe(true)
    expect(wrapper.find('.menu-element__compact-menu-trigger').exists()).toBe(
      true
    )
    expect(wrapper.find('.menu-element__menu-item-link').exists()).toBe(true)
    expect(wrapper.text()).toContain('Page')
  })

  test('does not open compact menu from trigger control in edit mode', async () => {
    const wrapper = await mountComponent({
      componentMode: mode,
      element: createElement({
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
      }),
    })

    await openCompactMenu(wrapper)

    expect(wrapper.find('.menu-element__container--compact').exists()).toBe(
      false
    )
  })

  test('opens compact menu in edit mode from editor state', async () => {
    const wrapper = await mountComponent({
      componentMode: mode,
      element: createElement({
        _: {
          compactMenuOpen: true,
        },
        variant: {
          desktop: 'compact',
          tablet: 'compact',
          smartphone: 'compact',
        },
      }),
    })

    expect(wrapper.find('.menu-element__container--compact').exists()).toBe(
      true
    )
    expect(
      wrapper.find('.menu-element__compact-menu-editor-overlay').exists()
    ).toBe(true)
    expect(wrapper.find('.menu-element__menu-item-link').exists()).toBe(true)
  })

  test('resets compact menu editor state when unmounted', async () => {
    const element = createElement({
      _: {
        compactMenuOpen: true,
      },
      variant: {
        desktop: 'compact',
        tablet: 'compact',
        smartphone: 'compact',
      },
    })
    const wrapper = await mountComponent({
      componentMode: mode,
      element,
    })

    wrapper.unmount()

    expect(element._.compactMenuOpen).toBe(false)
  })

  test('does not render compact menu editor overlay outside edit mode', async () => {
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

    expect(wrapper.find('.menu-element__container--compact').exists()).toBe(
      true
    )
    expect(
      wrapper.find('.menu-element__compact-menu-editor-overlay').exists()
    ).toBe(false)
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
      wrapper.find('.menu-element__container--compact').attributes('style')
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
    await wrapper.find('.menu-element__compact-menu-close').trigger('click')

    expect(wrapper.find('.menu-element__container--compact').exists()).toBe(
      false
    )
    expect(wrapper.find('.menu-element__compact-menu-trigger').exists()).toBe(
      true
    )
    expect(
      wrapper.find('.menu-element__compact-menu-trigger .iconoir-menu').exists()
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

    expect(wrapper.find('.menu-element__container--compact').exists()).toBe(
      false
    )
  })

  test('keeps the expanded menu when desktop variant is expanded', async () => {
    const wrapper = await mountComponent({
      element: createElement(),
    })

    expect(wrapper.find('.menu-element__compact-menu-trigger').exists()).toBe(
      false
    )
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
