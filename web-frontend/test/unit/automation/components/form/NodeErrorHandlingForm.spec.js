import { defineComponent, h } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import NodeErrorHandlingForm from '@baserow/modules/automation/components/form/NodeErrorHandlingForm.vue'

// The side panel provides the formula component the injected input renders.
// A stub stands in for it: the form only has to hand it the right props and
// pick up what it emits.
const FormulaInputStub = defineComponent({
  name: 'FormulaInputStub',
  props: {
    modelValue: { type: Object, default: null },
    enabledModes: { type: Array, default: () => [] },
    dataProvidersAllowed: { type: Array, default: () => [] },
    placeholder: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
  },
  emits: ['input'],
  render() {
    return h('div', { class: 'formula-input-stub' })
  },
})

const stopNode = {
  id: 1,
  type: 'http_request',
  on_failure: 'stop',
  max_retries: 2,
  retry_on_failure: true,
  retry_on_condition: false,
  retry_condition: { formula: '', mode: 'simple', version: '0.1' },
}

const retryNode = { ...stopNode, on_failure: 'retry' }

const mountForm = (node, { readOnly = false } = {}) =>
  mountSuspended(NodeErrorHandlingForm, {
    props: { node, readOnly },
    global: { provide: { formulaComponent: FormulaInputStub } },
  })

const segments = (wrapper) => wrapper.findAll('.segment-control__button')
const checkboxes = (wrapper) => wrapper.findAll('input.checkbox__native')
const retriesInput = (wrapper) => wrapper.find('input[type="number"]')
const conditionInput = (wrapper) => wrapper.findComponent(FormulaInputStub)

describe('NodeErrorHandlingForm', () => {
  test('stop shows no retry controls', async () => {
    const wrapper = await mountForm(stopNode)

    expect(segments(wrapper).map((el) => el.text())).toEqual([
      'nodeErrorHandlingForm.stop',
      'nodeErrorHandlingForm.retry',
    ])
    expect(segments(wrapper)[0].classes()).toContain(
      'segment-control__button--active'
    )
    expect(checkboxes(wrapper)).toHaveLength(0)
    expect(retriesInput(wrapper).exists()).toBe(false)
    expect(conditionInput(wrapper).exists()).toBe(false)
  })

  test('retry shows the reasons and the retries count', async () => {
    const wrapper = await mountForm(retryNode)

    expect(segments(wrapper)[1].classes()).toContain(
      'segment-control__button--active'
    )
    expect(checkboxes(wrapper).map((el) => el.element.checked)).toStrictEqual([
      true,
      false,
    ])
    expect(retriesInput(wrapper).element.value).toBe('2')
    expect(retriesInput(wrapper).element.disabled).toBe(false)
    // The condition input only takes room once its reason is ticked.
    expect(conditionInput(wrapper).exists()).toBe(false)
  })

  test('the retries count is disabled without a reason to retry', async () => {
    const wrapper = await mountForm({
      ...retryNode,
      retry_on_failure: false,
      retry_on_condition: false,
    })

    expect(retriesInput(wrapper).element.disabled).toBe(true)
  })

  test('a change emits only the changed key', async () => {
    const wrapper = await mountForm(stopNode)

    await segments(wrapper)[1].trigger('click')
    expect(wrapper.emitted('values-changed')).toEqual([
      [{ on_failure: 'retry' }],
    ])

    await checkboxes(wrapper)[1].setValue(true)
    expect(wrapper.emitted('values-changed')[1]).toEqual([
      { retry_on_condition: true },
    ])

    await checkboxes(wrapper)[0].setValue(false)
    expect(wrapper.emitted('values-changed')[2]).toEqual([
      { retry_on_failure: false },
    ])

    await retriesInput(wrapper).setValue('3')
    expect(wrapper.emitted('values-changed')[3]).toEqual([{ max_retries: 3 }])
  })

  test('an out of range retries count is shown as an error and not emitted', async () => {
    const wrapper = await mountForm(retryNode)

    await retriesInput(wrapper).setValue('7')
    expect(wrapper.emitted('values-changed')).toBeUndefined()
    expect(wrapper.find('.control__messages--error').text()).toBe(
      'error.maxValueField'
    )

    await retriesInput(wrapper).setValue('0')
    expect(wrapper.emitted('values-changed')).toBeUndefined()
    expect(wrapper.find('.control__messages--error').text()).toBe(
      'error.minValueField'
    )

    // Back in range, the error goes and the change is sent.
    await retriesInput(wrapper).setValue('5')
    expect(wrapper.emitted('values-changed')).toEqual([[{ max_retries: 5 }]])
    expect(wrapper.find('.control__messages--error').exists()).toBe(false)
  })

  test('the condition is edited in advanced mode only', async () => {
    // The API returns `simple` for the empty default, and an older node may
    // have stored the condition in simple mode: both open in advanced mode.
    const wrapper = await mountForm({
      ...retryNode,
      retry_on_condition: true,
      retry_condition: {
        formula: "get('current_node.status_code') = 503",
        mode: 'simple',
        version: '0.1',
      },
    })

    const input = conditionInput(wrapper)
    expect(input.exists()).toBe(true)
    expect(input.props('enabledModes')).toEqual(['advanced'])
    expect(input.props('modelValue')).toEqual({
      formula: "get('current_node.status_code') = 503",
      mode: 'advanced',
      version: '0.1',
    })
    // The node's own result is offered on top of what the service form gets.
    expect(input.props('dataProvidersAllowed')).toEqual([
      'current_node',
      'current_iteration',
      'previous_node',
    ])
    expect(input.props('placeholder')).toBe(
      'nodeErrorHandlingForm.conditionPlaceholder'
    )
  })

  test('an empty condition opens in advanced mode too', async () => {
    const wrapper = await mountForm({ ...retryNode, retry_on_condition: true })

    expect(conditionInput(wrapper).props('modelValue')).toEqual({
      formula: '',
      mode: 'advanced',
      version: '0.1',
    })
  })

  test('an edit of the condition is emitted as is', async () => {
    const wrapper = await mountForm({ ...retryNode, retry_on_condition: true })
    const condition = {
      formula: "get('current_node.status_code') = 429",
      mode: 'advanced',
      version: '0.1',
    }

    conditionInput(wrapper).vm.$emit('input', condition)

    expect(wrapper.emitted('values-changed')).toEqual([
      [{ retry_condition: condition }],
    ])
  })

  test('read only emits nothing', async () => {
    const wrapper = await mountForm(retryNode, { readOnly: true })

    await segments(wrapper)[0].trigger('click')
    await checkboxes(wrapper)[1].setValue(true)
    await retriesInput(wrapper).setValue('3')

    expect(wrapper.emitted('values-changed')).toBeUndefined()
    expect(segments(wrapper)[1].classes()).toContain(
      'segment-control__button--active'
    )
    expect(checkboxes(wrapper)[1].element.disabled).toBe(true)
    expect(retriesInput(wrapper).element.disabled).toBe(true)
  })

  test('follows the node when another one is selected', async () => {
    const wrapper = await mountForm(retryNode)
    expect(checkboxes(wrapper)).toHaveLength(2)

    await wrapper.setProps({ node: { ...stopNode, id: 2 } })

    expect(segments(wrapper)[0].classes()).toContain(
      'segment-control__button--active'
    )
    expect(checkboxes(wrapper)).toHaveLength(0)
    expect(wrapper.emitted('values-changed')).toBeUndefined()
  })
})
