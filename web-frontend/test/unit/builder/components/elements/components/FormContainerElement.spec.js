import { mountSuspended } from '@nuxt/test-utils/runtime'
import { reactive } from 'vue'
import FormContainerElement from '@baserow/modules/builder/components/elements/components/FormContainerElement.vue'
import { DATA_SCOPES } from '@baserow/modules/builder/constants'
import { SubmitEvent } from '@baserow/modules/builder/eventTypes'

describe('FormContainerElement', () => {
  let wrapper
  let submit

  beforeEach(() => {
    submit = vi.spyOn(SubmitEvent.prototype, 'fire').mockResolvedValue()
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.restoreAllMocks()
  })

  const mountForm = async ({ mode = 'public', nameOverrides = {} } = {}) => {
    const { $store: store } = useNuxtApp()
    const page = reactive({
      id: 1,
      elements: [],
      workflowActions: [],
      graph: {
        0: 41,
        41: { children: { '': [42] } },
        42: { next: { '': [43] } },
        43: {},
      },
    })
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const common = {
      page_id: page.id,
      css_classes: '',
      styles: {},
      style_background_file: null,
      visibility: 'all',
    }
    const form = {
      ...common,
      id: 41,
      type: 'form_container',
      submit_button_label: { formula: "'Submit'" },
      reset_initial_values_post_submission: false,
    }
    const type = {
      ...common,
      id: 42,
      type: 'choice',
      label: { formula: "'Type'" },
      default_value: { formula: '' },
      placeholder: { formula: '' },
      required: true,
      multiple: false,
      show_as_dropdown: true,
      option_type: 'manual',
      options: [
        { id: 1, value: '1', name: 'Type 1' },
        { id: 2, value: '2', name: 'Type 2' },
      ],
    }
    const name = {
      ...common,
      id: 43,
      type: 'input_text',
      label: { formula: "'Name'" },
      default_value: { formula: '' },
      placeholder: { formula: '' },
      required: true,
      validation_type: 'any',
      is_multiline: false,
      rows: 1,
      input_type: 'text',
      visibility_condition: {
        formula: "get('form_data.42') = '1'",
        mode: 'advanced',
      },
      ...nameOverrides,
    }
    for (const element of [form, type, name]) {
      await store.dispatch('element/forceCreate', { page, element })
    }
    const workspace = {}
    wrapper = await mountSuspended(FormContainerElement, {
      props: { element: form },
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          workspace,
          applicationContext: {
            builder,
            page,
            mode,
            workspace,
            element: form,
            dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
          },
        },
      },
    })
  }

  const selectType = async (index) => {
    await wrapper.get('.ab-dropdown__selected').trigger('click')
    await wrapper.findAll('.ab-dropdownitem__item-link')[index].trigger('click')
  }

  test.each(['public', 'preview'])(
    'validates a newly visible required field on submit in %s mode',
    async (mode) => {
      await mountForm({ mode })
      expect(wrapper.find('input[type="text"]').exists()).toBe(false)
      await selectType(0)
      expect(wrapper.get('input[type="text"]').element.value).toBe('')
      expect(wrapper.find('.ab-form-group__error-message').exists()).toBe(false)

      await wrapper.get('button').trigger('click')

      expect(wrapper.get('.ab-form-group__error-message').text()).toContain(
        'error.requiredField'
      )
      expect(submit).not.toHaveBeenCalled()

      await wrapper.get('input[type="text"]').setValue('Ada')
      expect(wrapper.find('.ab-form-group__error-message').exists()).toBe(false)
      await wrapper.get('button').trigger('click')
      expect(submit).toHaveBeenCalledOnce()
    }
  )

  test('does not validate a required field while its condition is false', async () => {
    await mountForm()
    await selectType(1)
    expect(wrapper.find('input[type="text"]').exists()).toBe(false)

    await wrapper.get('button').trigger('click')

    expect(wrapper.find('.ab-form-group__error-message').exists()).toBe(false)
    expect(submit).toHaveBeenCalledOnce()
  })

  test('validates again after hiding and showing an empty required field', async () => {
    await mountForm()
    await selectType(0)
    await wrapper.get('button').trigger('click')
    expect(wrapper.find('.ab-form-group__error-message').exists()).toBe(true)

    await selectType(1)
    await wrapper.get('button').trigger('click')
    expect(submit).toHaveBeenCalledOnce()

    await selectType(0)
    expect(wrapper.find('.ab-form-group__error-message').exists()).toBe(false)
    await wrapper.get('button').trigger('click')
    expect(wrapper.get('.ab-form-group__error-message').text()).toContain(
      'error.requiredField'
    )
    expect(submit).toHaveBeenCalledOnce()
  })

  test('does not validate a field hidden by an invalid visibility formula', async () => {
    await mountForm({
      nameOverrides: {
        visibility_condition: {
          formula: 'unknown_function()',
          mode: 'advanced',
        },
      },
    })
    await selectType(0)
    expect(wrapper.find('input[type="text"]').exists()).toBe(false)

    await wrapper.get('button').trigger('click')

    expect(wrapper.find('.ab-form-group__error-message').exists()).toBe(false)
    expect(submit).toHaveBeenCalledOnce()
  })
})
