import { reactive } from 'vue'
import { DOMWrapper } from '@vue/test-utils'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import PageElement from '@baserow/modules/builder/components/page/PageElement.vue'
import MenuElement from '@baserow/modules/builder/components/elements/components/MenuElement.vue'

describe('Clickable containers', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  const createElement = (id, type) => ({
    id,
    type,
    page_id: 1,
    css_classes: `qa-element-${id}`,
    styles: {},
    style_background_file: null,
    visibility: 'all',
    value: { mode: 'raw', formula: 'Child content' },
    format: 'plain',
    column_amount: 2,
    column_gap: 20,
    alignment: 'top',
    layout_type: 'auto',
    column_stacking: {},
    navigation_type: 'custom',
    navigate_to_url: { mode: 'raw', formula: 'https://example.com' },
    label: { mode: 'raw', formula: 'Name' },
    default_value: { mode: 'raw', formula: '' },
    placeholder: { mode: 'raw', formula: 'Enter a name' },
    required: false,
    validation_type: 'any',
    input_type: 'text',
    is_multiline: false,
    rows: 1,
  })

  const mountTree = async ({
    outerType = 'simple_container',
    innerType = 'column',
    childType = 'text',
    actionIds = [10, 11, 12],
    contextMode = 'public',
    applicationContextAdditions = {},
    title = null,
  } = {}) => {
    const elements = [
      createElement(10, outerType),
      createElement(11, innerType),
      createElement(12, childType),
    ]
    const page = reactive({
      id: 1,
      shared: false,
      elements: [],
      workflowActions: [],
      graph: {
        0: 10,
        10: { children: { [outerType === 'column' ? '0' : '']: [11] } },
        11: { children: { [innerType === 'column' ? '0' : '']: [12] } },
        12: {},
      },
    })
    const builder = { id: 1, theme: {}, pages: [page] }
    for (const element of elements) {
      await testApp.store.dispatch('element/forceCreate', { page, element })
    }
    for (const elementId of actionIds) {
      await testApp.store.dispatch('builderWorkflowAction/forceCreate', {
        page,
        workflowAction: {
          id: elementId * 10,
          element_id: elementId,
          page_id: page.id,
          event: 'click',
          type: 'notification',
          order: 1,
          title: title || { mode: 'raw', formula: `Element ${elementId}` },
          description: { mode: 'raw', formula: 'Action completed' },
        },
      })
    }
    const provide = {
      workspace: {},
      builder,
      currentPage: page,
      elementPage: page,
      mode: 'public',
      applicationContext: {
        builder,
        page,
        mode: contextMode,
        recordIndexPath: [],
        ...applicationContextAdditions,
      },
    }
    const wrapper = await testApp.mount(PageElement, {
      props: { element: elements[0] },
      global: { provide },
    })
    return { wrapper, provide }
  }

  const notifications = () => testApp.store.getters['builderToast/all']
  const notificationTitles = () => notifications().map(({ title }) => title)
  const getElement = (wrapper, id) => wrapper.get(`.qa-element-${id}`)
  const getSurface = (wrapper, id) =>
    new DOMWrapper(getElement(wrapper, id).element.parentElement)
  const getControl = (wrapper, id) => {
    const element = getElement(wrapper, id)
    return element.attributes('role') === 'button'
      ? element
      : getSurface(wrapper, id)
  }

  describe.each([
    ['simple_container', 'column'],
    ['column', 'simple_container'],
  ])('%s containing %s', (outerType, innerType) => {
    test('executes only the clicked display child action', async () => {
      const { wrapper } = await mountTree({ outerType, innerType })

      await getElement(wrapper, 12).get('.ab-text').trigger('click')
      await flushPromises()

      expect(notificationTitles()).toEqual(['Element 12'])
    })

    test('executes the nearest clickable parent for noninteractive content', async () => {
      const { wrapper } = await mountTree({
        outerType,
        innerType,
        actionIds: [10, 11],
      })

      await getElement(wrapper, 12).get('.ab-text').trigger('click')
      await flushPromises()

      expect(notificationTitles()).toEqual(['Element 11'])
    })

    test('reaches the outer action through a container without an action', async () => {
      const { wrapper } = await mountTree({
        outerType,
        innerType,
        actionIds: [10],
      })

      await getElement(wrapper, 12).get('.ab-text').trigger('click')
      await flushPromises()

      expect(notificationTitles()).toEqual(['Element 10'])
    })

    test('treats nested container padding as part of that container', async () => {
      const { wrapper } = await mountTree({ outerType, innerType })

      await getSurface(wrapper, 11).trigger('click')
      await flushPromises()

      expect(notificationTitles()).toEqual(['Element 11'])
    })

    test('activates only the container targeted by a keyboard event', async () => {
      const { wrapper } = await mountTree({
        outerType,
        innerType,
        actionIds: [10, 11],
      })
      const outer = getControl(wrapper, 10)
      const inner = getControl(wrapper, 11)
      expect(outer.attributes('tabindex')).toBe('0')
      expect(inner.attributes('tabindex')).toBe('0')

      await outer.trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(notificationTitles()).toEqual(['Element 10'])

      await getElement(wrapper, 12)
        .get('.ab-text')
        .trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(notificationTitles()).toEqual(['Element 10'])

      await inner.trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(notificationTitles()).toEqual(['Element 11', 'Element 10'])

      await inner.trigger('keydown', { key: ' ' })
      await inner.trigger('keyup', { key: ' ' })
      await flushPromises()
      expect(notificationTitles()).toEqual([
        'Element 11',
        'Element 11',
        'Element 10',
      ])
    })

    test('does not make containers interactive without a click action', async () => {
      const { wrapper } = await mountTree({
        outerType,
        innerType,
        actionIds: [],
      })

      for (const id of [10, 11]) {
        expect(getElement(wrapper, id).attributes('tabindex')).toBeUndefined()
        expect(getSurface(wrapper, id).attributes('tabindex')).toBeUndefined()
      }
      await getSurface(wrapper, 11).trigger('click')
      await flushPromises()

      expect(notifications()).toHaveLength(0)
    })

    test('does not activate repeated editor copies rendered in public mode', async () => {
      const { wrapper } = await mountTree({
        outerType,
        innerType,
        contextMode: 'editing',
        applicationContextAdditions: { recordIndexPath: [1], recordId: 42 },
      })

      for (const id of [10, 11, 12]) {
        expect(getControl(wrapper, id).attributes('tabindex')).toBeUndefined()
        await getSurface(wrapper, id).trigger('click')
        await getElement(wrapper, id).trigger('keydown', { key: 'Enter' })
        await getElement(wrapper, id).trigger('keyup', { key: ' ' })
      }
      await flushPromises()

      expect(notifications()).toHaveLength(0)
    })

    test('dismisses an open compact menu while executing its action', async () => {
      const { wrapper, provide } = await mountTree({ outerType, innerType })
      const menu = await testApp.mount(MenuElement, {
        props: {
          element: {
            id: 30,
            type: 'menu',
            page_id: 1,
            styles: {},
            variant: {
              desktop: 'compact',
              tablet: 'compact',
              smartphone: 'compact',
            },
            menu_items: [],
          },
        },
        global: { provide },
      })
      await menu
        .get('.menu-element__compact-menu-trigger-icon')
        .trigger('click')
      expect(menu.find('.menu-element__container--compact').exists()).toBe(true)

      await getSurface(wrapper, 10).trigger('mousedown')
      await getSurface(wrapper, 10).trigger('click')
      await flushPromises()

      expect(notificationTitles()).toEqual(['Element 10'])
      expect(menu.find('.menu-element__container--compact').exists()).toBe(
        false
      )
    })
  })

  test.each([
    ['button', 'button', ['Element 12']],
    ['link', 'a', []],
    ['input_text', 'input', []],
  ])(
    'keeps a child %s interaction separate from parent actions',
    async (childType, selector, expected) => {
      const { wrapper } = await mountTree({
        childType,
        actionIds: childType === 'button' ? [10, 11, 12] : [10, 11],
      })
      const control = getElement(wrapper, 12).get(selector)

      await control.trigger('click')
      await control.trigger('keydown', { key: 'Enter' })
      await control.trigger('keydown', { key: ' ' })
      await control.trigger('keyup', { key: ' ' })
      if (childType === 'input_text') {
        await control.setValue('Ada')
        expect(control.element.value).toBe('Ada')
      }
      await flushPromises()

      expect(notificationTitles()).toEqual(expected)
    }
  )

  test('keeps the current repeated record when a container handles its child click', async () => {
    const { wrapper } = await mountTree({
      actionIds: [11],
      applicationContextAdditions: { recordIndexPath: [2], recordId: 42 },
      title: { formula: "get('current_record.__idx__')" },
    })

    await getElement(wrapper, 12).get('.ab-text').trigger('click')
    await flushPromises()

    expect(notificationTitles()).toEqual(['2'])
  })
})
