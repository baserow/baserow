import MockAdapter from 'axios-mock-adapter'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import flushPromises from 'flush-promises'
import RepeatElement from '@baserow/modules/builder/components/elements/components/RepeatElement.vue'
import TableElement from '@baserow/modules/builder/components/elements/components/TableElement.vue'
import RecordSelectorElement from '@baserow/modules/builder/components/elements/components/RecordSelectorElement.vue'
import { DATA_SCOPES } from '@baserow/modules/builder/constants'

describe('collection footer formula scope', () => {
  let store
  let mock

  beforeEach(() => {
    const app = useNuxtApp()
    store = app.$store
    mock = new MockAdapter(app.$client, { onNoMatch: 'throwException' })
  })

  afterEach(() => {
    mock.restore()
  })

  const mountCollection = async ({
    type,
    nested = false,
    withField = false,
    withButton = false,
  }) => {
    const page = {
      id: 1,
      dataSources: [
        { id: 1, type: 'local_baserow_list_rows', table_id: 1 },
        { id: 2, type: 'local_baserow_list_rows', table_id: 1 },
      ],
      workflowActions: [],
      graph: nested
        ? {
            0: 10,
            10: { children: { '': [20] } },
            20: type === 'repeat' ? { children: { '': [30] } } : {},
            30: {},
          }
        : {
            0: 20,
            20: type === 'repeat' ? { children: { '': [30] } } : {},
            30: {},
          },
    }
    const sharedPage = { id: 2, shared: true, dataSources: [], graph: {} }
    const builder = {
      id: 1,
      theme: { primary_color: '#ccc' },
      pages: [sharedPage, page],
    }
    const parent = {
      id: 10,
      page_id: 1,
      type: 'repeat',
      data_source_id: 1,
      schema_property: null,
    }
    const element = {
      id: 20,
      page_id: 1,
      type,
      data_source_id: nested ? 2 : 1,
      schema_property: null,
      items_per_page: 1,
      items_per_row: { desktop: 1 },
      vertical_gap: 0,
      horizontal_gap: 0,
      button_load_more_label: { formula: "get('current_record.field_1')" },
      label: { formula: "get('current_record.field_1')" },
      placeholder: { formula: "get('current_record.field_1')" },
      default_value: { formula: "get('current_record.field_2')" },
      option_name_suffix: { formula: "get('current_record.field_1')" },
      fields: [
        ...(withField
          ? [
              {
                id: 1,
                type: 'text',
                name: 'Row name',
                value: { formula: "get('current_record.field_1')" },
                styles: {},
              },
            ]
          : []),
        ...(withButton
          ? [
              {
                id: 2,
                uid: 'notify-button',
                type: 'button',
                name: 'Notify',
                label: { formula: "'Notify'" },
                styles: {},
              },
            ]
          : []),
      ],
      orientation: { desktop: 'horizontal' },
      styles: {},
    }
    const child = {
      id: 30,
      page_id: 1,
      type: 'text',
      value: { formula: "'Child'" },
      styles: {},
    }
    store.commit('element/SET_ITEMS', {
      builder,
      page,
      elements: [
        ...(nested ? [parent] : []),
        element,
        ...(type === 'repeat' ? [child] : []),
      ],
    })
    if (withButton) {
      store.commit('builderWorkflowAction/SET_ITEMS', {
        page,
        workflowActions: [
          {
            id: 1,
            element_id: element.id,
            event: 'notify-button_click',
            order: 1,
            type: 'notification',
            title: { formula: "get('current_record.field_1')" },
            description: { formula: '' },
          },
        ],
      })
    }
    if (nested) {
      parent._.content = [
        { id: 1, field_1: 'Bread', field_2: 41 },
        { id: 2, field_1: 'Croissant', field_2: 42 },
      ]
    }
    element._.content = [
      { id: 3, field_1: 'Own first row', field_2: 98 },
      { id: 4, field_1: 'Own second row', field_2: 99 },
    ]
    mock
      .onPost(
        `builder/domains/published/data-source/${element.data_source_id}/dispatch/`
      )
      .reply(200, {
        results: [
          { id: 3, field_1: 'Own first row' },
          { id: 4, field_1: 'Own second row' },
        ],
        has_next_page: true,
      })

    const components = {
      repeat: RepeatElement,
      table: TableElement,
      record_selector: RecordSelectorElement,
    }
    const wrapper = await mountSuspended(components[type], {
      props: { element },
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode: 'public',
          applicationContext: {
            builder,
            page,
            mode: 'public',
            element,
            recordIndexPath: nested ? [1] : [],
            dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
          },
          workspace: {},
        },
        stubs: { PageElement: true },
      },
    })
    await flushPromises()
    return wrapper
  }

  test.each(['repeat', 'table'])(
    '%s footer cannot read its own first row',
    async (type) => {
      const wrapper = await mountCollection({ type })
      expect(wrapper.text()).toContain(`${type}Element.showMore`)
      expect(wrapper.text()).not.toContain('Own first row')
      wrapper.unmount()
    }
  )

  test('table cells can read their row while the footer cannot', async () => {
    const wrapper = await mountCollection({ type: 'table', withField: true })
    expect(wrapper.text()).toContain('Own first row')
    expect(wrapper.find('.table-element__footer').text()).toContain(
      'tableElement.showMore'
    )
    expect(wrapper.find('.table-element__footer').text()).not.toContain(
      'Own first row'
    )
    wrapper.unmount()
  })

  test('a table button action reads the clicked table row', async () => {
    const dispatch = vi.spyOn(store, 'dispatch')
    const wrapper = await mountCollection({ type: 'table', withButton: true })

    const buttons = wrapper.findAll('.ab-table__cell button')
    expect(buttons).toHaveLength(2)
    await buttons[1].trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('builderToast/info', {
      title: 'Own second row',
      titleFormat: undefined,
      message: '',
      messageFormat: undefined,
    })
    wrapper.unmount()
    dispatch.mockRestore()
  })

  test.each(['repeat', 'table'])(
    'nested %s footer reads its enclosing row, not its own row',
    async (type) => {
      const wrapper = await mountCollection({ type, nested: true })
      expect(wrapper.text()).toContain('Croissant')
      expect(wrapper.text()).not.toContain('Own second row')
      wrapper.unmount()
    }
  )

  test('record selector label cannot read its own row', async () => {
    const wrapper = await mountCollection({ type: 'record_selector' })
    expect(wrapper.vm.resolvedLabel).toBe('')
    expect(wrapper.vm.resolvedPlaceholder).toBe('')
    expect(wrapper.vm.resolvedDefaultValue).toBe(null)
    expect(
      wrapper.vm.elementType.getDisplayName(
        wrapper.vm.element,
        wrapper.vm.applicationContext
      )
    ).toBe('elementType.recordSelector')
    wrapper.unmount()
  })

  test('nested record selector label reads its enclosing row', async () => {
    const wrapper = await mountCollection({
      type: 'record_selector',
      nested: true,
    })
    expect(wrapper.vm.resolvedLabel).toBe('Croissant')
    expect(wrapper.vm.resolvedPlaceholder).toBe('Croissant')
    expect(wrapper.vm.resolvedDefaultValue).toBe(42)
    expect(
      wrapper.vm.elementType.getDisplayName(
        wrapper.vm.element,
        wrapper.vm.applicationContext
      )
    ).toBe('Croissant')
    wrapper.unmount()
  })

  test('record selector option suffix uses each option row, not the enclosing row', async () => {
    const wrapper = await mountCollection({
      type: 'record_selector',
      nested: true,
    })
    await wrapper.find('.ab-dropdown__selected').trigger('click')
    await flushPromises()

    const options = wrapper.findAll('.ab-dropdownitem__item-link')
    expect(options[0].text()).toContain('Own first row')
    expect(options[1].text()).toContain('Own second row')
    expect(options[0].text()).not.toContain('Croissant')
    wrapper.unmount()
  })
})
