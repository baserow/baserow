import { reactive } from 'vue'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import ChoiceElement from '@baserow/modules/builder/components/elements/components/ChoiceElement.vue'
import RecordSelectorElement from '@baserow/modules/builder/components/elements/components/RecordSelectorElement.vue'
import PageElement from '@baserow/modules/builder/components/page/PageElement.vue'
import { DATA_SCOPES } from '@baserow/modules/builder/constants'
import { CoreCSVFileReaderServiceType } from '@baserow/modules/integrations/core/serviceTypes'

class StringRecordIdServiceType extends CoreCSVFileReaderServiceType {
  static getType() {
    return 'test_selection_string_ids'
  }

  parseRecordId(value) {
    return value === '' || value === null ? null : String(value)
  }

  getRecordIdDataType() {
    return 'string'
  }
}

describe('Selection change workflows', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
    testApp
      .getRegistry()
      .register(
        'service',
        new StringRecordIdServiceType({ app: testApp.getApp() })
      )
  })

  afterEach(async () => {
    if (vi.isFakeTimers()) {
      await vi.runOnlyPendingTimersAsync()
      vi.useRealTimers()
    }
    vi.restoreAllMocks()
    await testApp.afterEach()
    testApp
      .getRegistry()
      .unregister('service', StringRecordIdServiceType.getType())
  })

  const source = (id, type = 'csv_file_reader') => ({
    id,
    type,
    name: 'Options',
    schema: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: type === 'csv_file_reader' ? 'number' : 'string' },
          name: { type: 'string', searchable: true },
        },
      },
    },
  })

  const mountSelection = async (
    type,
    {
      elementValues = {},
      mode = 'public',
      contextMode = mode,
      withForm = false,
      withRepeat = false,
      stringIds = false,
      recordsPromise = null,
    } = {}
  ) => {
    const values = stringIds ? ['group-a', 'group-b'] : [1, 2]
    const records = values.map((id, index) => ({
      id,
      name: index === 0 ? 'Alpha' : 'Beta',
    }))
    const dataSources = [
      source(1, stringIds ? StringRecordIdServiceType.getType() : undefined),
      source(2),
    ]
    const element = reactive({
      id: 12,
      type,
      page_id: 1,
      css_classes: 'qa-selection',
      styles: {},
      style_background_file: null,
      visibility: 'all',
      label: { mode: 'raw', formula: 'Selection' },
      placeholder: { mode: 'raw', formula: 'Choose an option' },
      default_value: { mode: 'raw', formula: '' },
      required: false,
      multiple: false,
      show_as_dropdown: true,
      show_search: true,
      option_type: 'manual',
      options: [
        { id: 1, value: 'alpha', name: 'Alpha' },
        { id: 2, value: 'beta', name: 'Beta' },
        { id: 3, value: 'gamma', name: 'Gamma' },
      ],
      data_source_id: type === 'record_selector' ? 1 : null,
      items_per_page: 10,
      property_options: [{ schema_property: 'name', searchable: true }],
      option_name_suffix: { mode: 'raw', formula: '' },
      ...elementValues,
    })
    const form = {
      ...element,
      id: 11,
      type: 'form_container',
      css_classes: 'qa-form',
      submit_button_label: { mode: 'raw', formula: 'Submit' },
      reset_initial_values_post_submission: true,
    }
    const repeat = {
      ...element,
      id: 10,
      type: 'repeat',
      data_source_id: 2,
      schema_property: null,
    }
    const graph = { 12: {} }
    if (withForm) {
      graph[11] = { children: { '': [12] } }
    }
    if (withRepeat) {
      graph[10] = { children: { '': [withForm ? 11 : 12] } }
    }
    graph[0] = withRepeat ? 10 : withForm ? 11 : 12
    const page = reactive({
      id: 1,
      path: '/',
      path_params: [],
      query_params: [],
      shared: false,
      dataSources,
      elements: [],
      workflowActions: [],
      graph,
    })
    const sharedPage = { id: 2, shared: true, elements: [], dataSources: [] }
    const builder = { id: 1, theme: {}, pages: [page, sharedPage] }
    for (const item of [
      ...(withRepeat ? [repeat] : []),
      ...(withForm ? [form] : []),
      element,
    ]) {
      await testApp.store.dispatch('element/forceCreate', {
        page,
        element: item,
      })
    }
    if (withRepeat) {
      testApp.store.commit('elementContent/SET_CONTENT', {
        element: repeat,
        value: [
          { id: 101, name: 'Outer Alpha' },
          { id: 102, name: 'Outer Beta' },
        ],
      })
    }
    await testApp.store.dispatch('builderWorkflowAction/forceCreate', {
      page,
      workflowAction: {
        id: 20,
        element_id: element.id,
        page_id: page.id,
        type: 'notification',
        event: 'change',
        order: 1,
        title: { formula: "get('form_data.12')" },
        description: withRepeat
          ? { formula: "get('current_record.name')" }
          : { mode: 'raw', formula: 'Selection changed' },
      },
    })
    if (withForm) {
      await testApp.store.dispatch('builderWorkflowAction/forceCreate', {
        page,
        workflowAction: {
          id: 21,
          element_id: form.id,
          page_id: page.id,
          type: 'notification',
          event: 'submit',
          order: 1,
          title: { mode: 'raw', formula: 'Form submitted' },
          description: { mode: 'raw', formula: '' },
        },
      })
    }
    testApp.mock
      .onPost(/builder\/(?:domains\/published\/)?data-source\/1\/dispatch\//)
      .reply(() =>
        recordsPromise
          ? recordsPromise.then(() => [
              200,
              { results: records, has_next_page: false },
            ])
          : [200, { results: records, has_next_page: false }]
      )
    testApp.mock
      .onGet(/builder\/(?:domains\/published\/)?data-source\/1\/record-names\//)
      .reply(200, Object.fromEntries(records.map(({ id, name }) => [id, name])))
    const root = withForm ? form : element
    const wrapper = await testApp.mount(
      withForm
        ? PageElement
        : type === 'choice'
          ? ChoiceElement
          : RecordSelectorElement,
      {
        props: { element: root },
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
              element: root,
              mode: contextMode,
              dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
              recordIndexPath: withRepeat ? [1] : [],
              ...(withRepeat ? { recordId: 102 } : {}),
            },
          },
        },
      }
    )
    if (type === 'record_selector' && element.default_value.formula) {
      await vi.waitFor(() => expect(testApp.mock.history.get).toHaveLength(1))
      await flushPromises()
    }
    return {
      wrapper,
      element,
      page,
      builder,
      values: type === 'choice' ? ['alpha', 'beta'] : values,
    }
  }

  const notifications = () => testApp.store.getters['builderToast/all']
  const titles = () => notifications().map(({ title }) => title)
  const open = async (wrapper) => {
    await wrapper.get('.ab-dropdown__selected').trigger('click')
    await flushPromises()
    await vi.waitFor(() =>
      expect(
        wrapper.findAll('.ab-dropdownitem__item-link').length
      ).toBeGreaterThanOrEqual(2)
    )
  }
  const choose = async (wrapper, index) => {
    await open(wrapper)
    await wrapper.findAll('.ab-dropdownitem__item-link')[index].trigger('click')
    await flushPromises()
  }
  const close = async (wrapper) => {
    await wrapper.get('.ab-dropdown').trigger('focusout', {
      relatedTarget: document.createElement('button'),
    })
    await flushPromises()
  }

  describe.each(['choice', 'record_selector'])('%s', (type) => {
    test('runs one change workflow with the updated form value', async () => {
      const { wrapper, values } = await mountSelection(type)
      expect(notifications()).toHaveLength(0)

      await choose(wrapper, 1)

      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe('Beta')
      expect(notifications()).toMatchObject([
        {
          type: 'info-primary',
          title: String(values[1]),
          message: 'Selection changed',
        },
      ])
    })

    test('exposes the changed value inside a form without firing on reset', async () => {
      const initial = type === 'choice' ? 'alpha' : '1'
      const { wrapper, values } = await mountSelection(type, {
        withForm: true,
        elementValues: { default_value: { mode: 'raw', formula: initial } },
      })
      await choose(wrapper, 1)
      expect(titles()).toEqual([String(values[1])])

      await wrapper
        .get('.form-container-element__submit-button button')
        .trigger('click')
      await flushPromises()

      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe('Alpha')
      expect(titles()).toEqual(['Form submitted', String(values[1])])
    })

    test('retains the enclosing repeated record with a different selector source', async () => {
      const { wrapper, values } = await mountSelection(type, {
        withRepeat: true,
      })

      await choose(wrapper, 1)

      expect(notifications()).toMatchObject([
        { title: String(values[1]), message: 'Outer Beta' },
      ])
    })

    test.each(['editing', 'public'])(
      'does not run workflows in an editor copy rendered in %s mode',
      async (mode) => {
        const { wrapper } = await mountSelection(type, {
          mode,
          contextMode: 'editing',
          withRepeat: true,
        })

        await choose(wrapper, 1)

        expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe('Beta')
        expect(notifications()).toHaveLength(0)
      }
    )

    test('does not fire on equal array store updates or changed default formulas', async () => {
      const { wrapper, element, page, builder, values } = await mountSelection(
        type,
        {
          elementValues: { multiple: true },
        }
      )
      await choose(wrapper, 0)
      expect(titles()).toEqual([String(values[0])])

      await testApp.store.dispatch('formData/setFormData', {
        page,
        uniqueElementId: '12',
        payload: {
          value: [values[0]],
          elementId: 12,
          type: 'array',
          isValid: true,
        },
      })
      await flushPromises()
      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe('Alpha')
      expect(notifications()).toHaveLength(1)

      vi.useFakeTimers()
      await testApp.store.dispatch('element/forceUpdate', {
        builder,
        page,
        element,
        values: { default_value: { mode: 'raw', formula: String(values[1]) } },
      })
      await vi.advanceTimersByTimeAsync(600)
      await flushPromises()

      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe('Beta')
      expect(notifications()).toHaveLength(1)
    })

    test('does not fire while opening, searching, closing or loading options', async () => {
      const { wrapper } = await mountSelection(type)
      await open(wrapper)
      expect(notifications()).toHaveLength(0)

      vi.useFakeTimers()
      const search = wrapper.get('.select__search-input')
      await search.setValue('Beta')
      await search.trigger('keyup')
      await vi.advanceTimersByTimeAsync(600)
      await flushPromises()
      await close(wrapper)
      await open(wrapper)

      expect(notifications()).toHaveLength(0)
      expect(wrapper.find('.ab-dropdown__selected-text').exists()).toBe(false)
    })

    test('blocks selection changes until the current workflow completes', async () => {
      const actionType = testApp
        .getRegistry()
        .get('workflowAction', 'notification')
      const execute = actionType.execute.bind(actionType)
      let finish
      const pending = new Promise((resolve) => {
        finish = resolve
      })
      vi.spyOn(actionType, 'execute').mockImplementationOnce((args) => {
        const result = execute(args)
        return pending.then(() => result)
      })
      const { wrapper, values } = await mountSelection(type)
      await choose(wrapper, 0)
      expect(titles()).toEqual([String(values[0])])

      await open(wrapper)
      expect(
        wrapper
          .findAll('.ab-dropdownitem__item')
          .every((item) => item.classes().includes('disabled'))
      ).toBe(true)
      await wrapper.findAll('.ab-dropdownitem__item-link')[1].trigger('click')
      await flushPromises()

      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe('Alpha')
      expect(notifications()).toHaveLength(1)

      finish()
      await flushPromises()
      const nextIndex = type === 'choice' ? 2 : 1
      await choose(wrapper, nextIndex)

      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe(
        type === 'choice' ? 'Gamma' : 'Beta'
      )
      expect(notifications()).toHaveLength(2)
    })
  })

  test('does not fire when a required dropdown option is selected again', async () => {
    const { wrapper } = await mountSelection('choice', {
      elementValues: {
        required: true,
        default_value: { mode: 'raw', formula: 'alpha' },
      },
    })
    await choose(wrapper, 0)
    expect(notifications()).toHaveLength(0)

    await choose(wrapper, 1)
    await choose(wrapper, 1)

    expect(titles()).toEqual(['beta'])
  })

  test('fires once when an optional choice is cleared', async () => {
    const { wrapper } = await mountSelection('choice', {
      elementValues: { default_value: { mode: 'raw', formula: 'alpha' } },
    })

    await choose(wrapper, 0)

    expect(wrapper.get('.ab-dropdown__selected-placeholder').text()).toBe(
      'Choose an option'
    )
    expect(titles()).toEqual([''])
  })

  test('fires for a different radio option, not for an unchanged selection', async () => {
    const { wrapper } = await mountSelection('choice', {
      elementValues: {
        show_as_dropdown: false,
        default_value: { mode: 'raw', formula: 'alpha' },
      },
    })
    const radios = wrapper.findAll('.ab-radio')

    await radios[0].trigger('click')
    await flushPromises()
    expect(notifications()).toHaveLength(0)

    await radios[1].trigger('click')
    await flushPromises()
    await radios[1].trigger('click')
    await flushPromises()

    expect(radios[1].get('input').element.checked).toBe(true)
    expect(titles()).toEqual(['beta'])
  })

  test.each([true, false])(
    'fires once per multiple choice addition/removal with dropdown=%s',
    async (dropdown) => {
      const { wrapper } = await mountSelection('choice', {
        elementValues: { multiple: true, show_as_dropdown: dropdown },
      })
      const toggle = async (index, checked) => {
        if (dropdown) {
          await choose(wrapper, index)
        } else {
          await wrapper.findAll('.ab-checkbox input')[index].setValue(checked)
          await flushPromises()
        }
      }

      await toggle(0, true)
      await toggle(1, true)
      await toggle(0, false)
      await toggle(1, false)

      expect(titles()).toEqual(['', 'beta', 'alpha,beta', 'alpha'])
    }
  )

  test.each([false, true])(
    'supports changed, identical and cleared record ids with stringIds=%s',
    async (stringIds) => {
      const values = stringIds ? ['group-a', 'group-b'] : [1, 2]
      const { wrapper } = await mountSelection('record_selector', {
        stringIds,
        elementValues: {
          required: true,
          default_value: { mode: 'raw', formula: String(values[0]) },
        },
      })
      await choose(wrapper, 0)
      expect(notifications()).toHaveLength(0)

      await choose(wrapper, 1)
      await choose(wrapper, 1)
      expect(titles()).toEqual([String(values[1])])
    }
  )

  test.each([false, true])(
    'clears an optional record selection with stringIds=%s',
    async (stringIds) => {
      const { wrapper, values } = await mountSelection('record_selector', {
        stringIds,
      })

      await choose(wrapper, 0)
      await choose(wrapper, 0)
      await choose(wrapper, 1)

      expect(titles()).toEqual([String(values[1]), '', String(values[0])])
    }
  )

  test.each([false, true])(
    'fires once per multiple record addition/removal with stringIds=%s',
    async (stringIds) => {
      const { wrapper, values } = await mountSelection('record_selector', {
        stringIds,
        elementValues: { multiple: true },
      })

      await choose(wrapper, 0)
      await choose(wrapper, 1)
      await choose(wrapper, 0)
      await choose(wrapper, 1)

      expect(titles()).toEqual([
        '',
        String(values[1]),
        values.join(','),
        String(values[0]),
      ])
    }
  )

  test('does not fire while a record selector request is pending', async () => {
    let resolveRecords
    const recordsPromise = new Promise((resolve) => {
      resolveRecords = resolve
    })
    const { wrapper } = await mountSelection('record_selector', {
      recordsPromise,
    })

    await wrapper.get('.ab-dropdown__selected').trigger('click')
    await flushPromises()
    expect(wrapper.find('.loading').exists()).toBe(true)
    expect(notifications()).toHaveLength(0)

    resolveRecords()
    await flushPromises()

    await vi.waitFor(() =>
      expect(wrapper.findAll('.ab-dropdownitem__item-link')).toHaveLength(2)
    )
    expect(notifications()).toHaveLength(0)
  })
})
