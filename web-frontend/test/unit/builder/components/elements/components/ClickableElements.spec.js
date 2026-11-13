import { reactive } from 'vue'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import HeadingElement from '@baserow/modules/builder/components/elements/components/HeadingElement.vue'
import TextElement from '@baserow/modules/builder/components/elements/components/TextElement.vue'
import ImageElement from '@baserow/modules/builder/components/elements/components/ImageElement.vue'
import MenuElement from '@baserow/modules/builder/components/elements/components/MenuElement.vue'
import clickOutside from '@baserow/modules/core/directives/clickOutside'

describe('Clickable display elements', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  const mountElement = async (
    component,
    type,
    {
      mode = 'public',
      contextMode = mode,
      withAction = true,
      elementValues = {},
      applicationContextAdditions = {},
      title = { mode: 'raw', formula: 'Clicked' },
    } = {}
  ) => {
    const element = {
      id: 10,
      page_id: 1,
      type,
      styles: {},
      value: { mode: 'raw', formula: 'Display content' },
      level: 2,
      format: 'plain',
      image_source_type: 'url',
      image_url: { mode: 'raw', formula: 'https://example.com/logo.png' },
      alt_text: { mode: 'raw', formula: 'Company logo' },
      ...elementValues,
    }
    const page = reactive({
      id: 1,
      elements: [element],
      workflowActions: [],
      graph: { 0: element.id, [element.id]: {} },
    })
    const builder = { id: 1, theme: {}, pages: [page] }
    if (withAction) {
      await testApp.store.dispatch('builderWorkflowAction/forceCreate', {
        page,
        workflowAction: {
          id: 20,
          element_id: element.id,
          page_id: page.id,
          event: 'click',
          type: 'notification',
          order: 1,
          title,
          description: { mode: 'raw', formula: 'Action completed' },
        },
      })
    }
    return testApp.mount(component, {
      props: { element, applicationContextAdditions },
      global: {
        provide: {
          workspace: {},
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext: {
            builder,
            page,
            element,
            mode: contextMode,
            recordIndexPath: [],
          },
        },
      },
    })
  }

  const notifications = () => testApp.store.getters['builderToast/all']

  const mountCompactMenu = async () => {
    const element = {
      id: 30,
      page_id: 1,
      type: 'menu',
      styles: {},
      orientation: 'horizontal',
      alignment: 'left',
      variant: {
        desktop: 'compact',
        tablet: 'compact',
        smartphone: 'compact',
      },
      menu_items: [
        {
          id: 1,
          uid: 'menu-item-1',
          type: 'link',
          name: 'Menu page',
          variant: 'link',
          navigation_type: 'custom',
          navigate_to_url: { mode: 'raw', formula: 'https://example.com' },
          parent_menu_item: null,
          children: [],
        },
      ],
    }
    const page = { id: 1, elements: [element], workflowActions: [] }
    const builder = { id: 1, theme: {}, pages: [page] }
    return testApp.mount(MenuElement, {
      props: { element },
      global: {
        directives: { clickOutside },
        provide: {
          workspace: {},
          builder,
          currentPage: page,
          elementPage: page,
          mode: 'public',
          applicationContext: { builder, page, element, mode: 'public' },
        },
      },
    })
  }

  describe.each([
    ['heading', HeadingElement, '.ab-heading'],
    ['text', TextElement, '.ab-text'],
    ['image', ImageElement, 'img'],
  ])('%s', (type, component, contentSelector) => {
    test('executes the configured workflow when its content is clicked', async () => {
      const wrapper = await mountElement(component, type)

      expect(wrapper.attributes('role')).toBe('button')
      expect(wrapper.attributes('tabindex')).toBe('0')
      expect(wrapper.classes()).toContain('element--clickable')
      await wrapper.get(contentSelector).trigger('click')
      await flushPromises()

      expect(notifications()).toMatchObject([
        { type: 'info-primary', title: 'Clicked', message: 'Action completed' },
      ])
    })

    test('supports Enter and Space without firing Space until keyup', async () => {
      const wrapper = await mountElement(component, type)

      await wrapper.trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(notifications()).toHaveLength(1)

      const space = new KeyboardEvent('keydown', {
        key: ' ',
        bubbles: true,
        cancelable: true,
      })
      wrapper.element.dispatchEvent(space)
      await flushPromises()
      expect(space.defaultPrevented).toBe(true)
      expect(notifications()).toHaveLength(1)

      await wrapper.trigger('keyup', { key: ' ' })
      await flushPromises()
      expect(notifications()).toHaveLength(2)
    })

    test('remains noninteractive without a configured click action', async () => {
      const wrapper = await mountElement(component, type, { withAction: false })

      expect(wrapper.attributes('role')).toBeUndefined()
      expect(wrapper.attributes('tabindex')).toBeUndefined()
      expect(wrapper.classes()).not.toContain('element--clickable')
      await wrapper.get(contentSelector).trigger('click')
      await wrapper.trigger('keydown', { key: 'Enter' })
      await wrapper.trigger('keyup', { key: ' ' })
      await flushPromises()
      expect(notifications()).toHaveLength(0)
    })

    test('dismisses an open compact menu while executing its workflow', async () => {
      const wrapper = await mountElement(component, type)
      const menu = await mountCompactMenu()
      await menu
        .get('.menu-element__compact-menu-trigger-icon')
        .trigger('click')
      expect(menu.get('.menu-element__container--compact').text()).toContain(
        'Menu page'
      )

      await wrapper.get(contentSelector).trigger('mousedown')
      await wrapper.get(contentSelector).trigger('click')
      await flushPromises()

      expect(notifications()).toMatchObject([
        { type: 'info-primary', title: 'Clicked', message: 'Action completed' },
      ])
      expect(menu.find('.menu-element__container--compact').exists()).toBe(
        false
      )
    })
  })

  test('executes workflows in preview mode', async () => {
    const wrapper = await mountElement(TextElement, 'text', { mode: 'preview' })

    await wrapper.get('.ab-text').trigger('click')
    await flushPromises()

    expect(notifications()).toMatchObject([{ title: 'Clicked' }])
  })

  test.each(['editing', 'public'])(
    'does not execute in the editor when the rendered mode is %s',
    async (mode) => {
      const wrapper = await mountElement(HeadingElement, 'heading', {
        mode,
        contextMode: 'editing',
      })

      expect(wrapper.attributes('tabindex')).toBeUndefined()
      await wrapper.get('.ab-heading').trigger('click')
      await wrapper.trigger('keydown', { key: 'Enter' })
      await wrapper.trigger('keyup', { key: ' ' })
      await flushPromises()

      expect(notifications()).toHaveLength(0)
    }
  )

  test('resolves workflow formulas using the clicked repeated record', async () => {
    const wrapper = await mountElement(TextElement, 'text', {
      applicationContextAdditions: { recordIndexPath: [2], recordId: 42 },
      title: { formula: "get('current_record.__idx__')" },
    })

    await wrapper.get('.ab-text').trigger('click')
    await flushPromises()

    expect(notifications()).toMatchObject([{ title: '2' }])
  })

  test('preserves Markdown links without triggering the text workflow', async () => {
    const wrapper = await mountElement(TextElement, 'text', {
      elementValues: {
        format: 'markdown',
        value: {
          mode: 'raw',
          formula: '[**Visit**](https://example.com)\n\nOther text',
        },
      },
    })
    const link = wrapper.get('a')

    expect(link.attributes('href')).toBe('https://example.com')
    await link.get('strong').trigger('click')
    await link.trigger('keydown', { key: 'Enter' })
    await link.trigger('keydown', { key: ' ' })
    await link.trigger('keyup', { key: ' ' })
    await flushPromises()
    expect(notifications()).toHaveLength(0)

    await wrapper.findAll('.ab-text')[1].trigger('click')
    await flushPromises()
    expect(notifications()).toMatchObject([{ title: 'Clicked' }])
  })
})
