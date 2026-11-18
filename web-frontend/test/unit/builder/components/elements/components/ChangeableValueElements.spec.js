import { reactive } from 'vue'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import CheckboxElement from '@baserow/modules/builder/components/elements/components/CheckboxElement.vue'
import RatingInputElement from '@baserow/modules/builder/components/elements/components/RatingInputElement.vue'
import PageElement from '@baserow/modules/builder/components/page/PageElement.vue'
import { DATA_SCOPES } from '@baserow/modules/builder/constants'

const CASES = {
  checkbox: {
    component: CheckboxElement,
    initial: 'false',
    initialFormula: { default_value: { mode: 'raw', formula: 'false' } },
    // The first and second user changes and the value each one stores.
    changed: ['true', 'false'],
    // A click toggles the native checkbox, as a user would.
    change: async (wrapper) => {
      await wrapper.get('.ab-checkbox input').trigger('click')
      await flushPromises()
    },
    current: (wrapper) => wrapper.get('.ab-checkbox input').element.checked,
    initialValue: false,
    changedValue: true,
    isBlocked: (wrapper) =>
      wrapper.get('.ab-checkbox input').attributes('disabled') !== undefined,
  },
  rating_input: {
    component: RatingInputElement,
    initial: '1',
    initialFormula: { value: { mode: 'raw', formula: '1' } },
    changed: ['3', '4'],
    change: async (wrapper, step) => {
      await wrapper
        .findAll('.rating__star')
        [step === 0 ? 2 : 3].trigger('click')
      await flushPromises()
    },
    current: (wrapper) => wrapper.findAll('.rating__star--selected').length,
    initialValue: 1,
    changedValue: 3,
    isBlocked: (wrapper) =>
      !wrapper.get('.rating').classes().includes('editing'),
  },
}

describe('Value change workflows', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    if (vi.isFakeTimers()) {
      await vi.runOnlyPendingTimersAsync()
      vi.useRealTimers()
    }
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  const mountValueElement = async (
    type,
    {
      elementValues = {},
      mode = 'public',
      contextMode = mode,
      withForm = false,
      withRepeat = false,
    } = {}
  ) => {
    const element = reactive({
      id: 12,
      type,
      page_id: 1,
      css_classes: 'qa-value',
      styles: {},
      style_background_file: null,
      visibility: 'all',
      label: { mode: 'raw', formula: 'Value' },
      required: false,
      max_value: 5,
      color: 'primary',
      rating_style: 'star',
      ...CASES[type].initialFormula,
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
      dataSources: [
        {
          id: 2,
          type: 'csv_file_reader',
          name: 'Records',
          schema: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'number' },
                name: { type: 'string' },
              },
            },
          },
        },
      ],
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
          : { mode: 'raw', formula: 'Value changed' },
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
    const root = withForm ? form : element
    const wrapper = await testApp.mount(
      withForm ? PageElement : CASES[type].component,
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
    await flushPromises()
    return { wrapper, element, page, builder }
  }

  const notifications = () => testApp.store.getters['builderToast/all']
  const titles = () => notifications().map(({ title }) => title)

  describe.each(Object.keys(CASES))('%s', (type) => {
    const { change, current, changed, initialValue, changedValue, isBlocked } =
      CASES[type]

    test('runs one change workflow per user change with the new form value', async () => {
      const { wrapper } = await mountValueElement(type)
      expect(current(wrapper)).toBe(initialValue)
      expect(notifications()).toHaveLength(0)

      await change(wrapper, 0)

      expect(current(wrapper)).toBe(changedValue)
      expect(notifications()).toMatchObject([
        { type: 'info-primary', title: changed[0], message: 'Value changed' },
      ])

      await change(wrapper, 1)

      // Toasts are listed newest first.
      expect(titles()).toEqual([changed[1], changed[0]])
    })

    test('exposes the changed value inside a form without firing on reset', async () => {
      const { wrapper } = await mountValueElement(type, { withForm: true })
      await change(wrapper, 0)
      expect(titles()).toEqual([changed[0]])

      await wrapper
        .get('.form-container-element__submit-button button')
        .trigger('click')
      await flushPromises()

      expect(current(wrapper)).toBe(initialValue)
      expect(titles()).toEqual(['Form submitted', changed[0]])
    })

    test('reads the enclosing repeated record', async () => {
      const { wrapper } = await mountValueElement(type, { withRepeat: true })

      await change(wrapper, 0)

      expect(notifications()).toMatchObject([
        { title: changed[0], message: 'Outer Beta' },
      ])
    })

    test.each(['editing', 'public'])(
      'does not run workflows in an editor copy rendered in %s mode',
      async (mode) => {
        const { wrapper } = await mountValueElement(type, {
          mode,
          contextMode: 'editing',
          withRepeat: true,
        })

        await change(wrapper, 0)

        expect(notifications()).toHaveLength(0)
      }
    )

    test('does not fire on equal store updates or changed default formulas', async () => {
      const { wrapper, element, page, builder } = await mountValueElement(type)
      await change(wrapper, 0)
      expect(notifications()).toHaveLength(1)

      await testApp.store.dispatch('formData/setFormData', {
        page,
        uniqueElementId: '12',
        payload: {
          value: changedValue,
          elementId: 12,
          type: type === 'checkbox' ? 'boolean' : 'number',
          isValid: true,
        },
      })
      await flushPromises()
      expect(notifications()).toHaveLength(1)

      vi.useFakeTimers()
      const formulaKey = Object.keys(CASES[type].initialFormula)[0]
      await testApp.store.dispatch('element/forceUpdate', {
        builder,
        page,
        element,
        values: {
          [formulaKey]: {
            mode: 'raw',
            formula: type === 'checkbox' ? 'true' : '5',
          },
        },
      })
      await vi.advanceTimersByTimeAsync(600)
      await flushPromises()

      expect(notifications()).toHaveLength(1)
    })

    test('blocks changes until the current workflow completes', async () => {
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
      const { wrapper } = await mountValueElement(type)
      await change(wrapper, 0)
      expect(titles()).toEqual([changed[0]])
      expect(isBlocked(wrapper)).toBe(true)

      await change(wrapper, 1)

      expect(current(wrapper)).toBe(changedValue)
      expect(notifications()).toHaveLength(1)

      finish()
      await flushPromises()
      expect(isBlocked(wrapper)).toBe(false)
      await change(wrapper, 1)

      // Toasts are listed newest first.
      expect(titles()).toEqual([changed[1], changed[0]])
    })
  })

  test('fires once when the checkbox label is clicked', async () => {
    const { wrapper } = await mountValueElement('checkbox')

    await wrapper.get('.ab-checkbox__label').trigger('click')
    await flushPromises()

    expect(wrapper.get('.ab-checkbox input').element.checked).toBe(true)
    expect(titles()).toEqual(['true'])
  })

  test('fires once when the selected rating is clicked to clear it', async () => {
    const { wrapper } = await mountValueElement('rating_input')

    await wrapper.findAll('.rating__star')[0].trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.rating__star--selected')).toHaveLength(0)
    expect(titles()).toEqual(['0'])
  })
})
