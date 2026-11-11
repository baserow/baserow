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
  retry_condition: { formula: '', mode: 'simple', version: '0.1' },
}

const retryNode = { ...stopNode, on_failure: 'retry' }

const mountForm = (node, { readOnly = false } = {}) =>
  mountSuspended(NodeErrorHandlingForm, {
    props: { node, readOnly },
    global: { provide: { formulaComponent: FormulaInputStub } },
  })

const segments = (wrapper) => wrapper.findAll('.segment-control__button')
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
    expect(retriesInput(wrapper).exists()).toBe(false)
    expect(conditionInput(wrapper).exists()).toBe(false)
  })

  test('retry shows the retries count and the condition', async () => {
    const wrapper = await mountForm(retryNode)

    expect(segments(wrapper)[1].classes()).toContain(
      'segment-control__button--active'
    )
    expect(retriesInput(wrapper).element.value).toBe('2')
    expect(retriesInput(wrapper).element.disabled).toBe(false)
    // A transient failure always retries under Retry; a condition is an
    // optional extra reason, so its input is always offered.
    expect(conditionInput(wrapper).exists()).toBe(true)
    expect(conditionInput(wrapper).props('disabled')).toBe(false)
  })

  test('a change emits only the changed key', async () => {
    const wrapper = await mountForm(stopNode)

    await segments(wrapper)[1].trigger('click')
    expect(wrapper.emitted('values-changed')).toEqual([
      [{ on_failure: 'retry' }],
    ])

    await retriesInput(wrapper).setValue('3')
    expect(wrapper.emitted('values-changed')[1]).toEqual([{ max_retries: 3 }])
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

  test('the condition input is restricted to advanced mode', async () => {
    // The stored value is passed as is: the API returns `simple` for the empty
    // default, and an older node may hold a simple-mode condition. The input
    // itself falls back to advanced mode when the stored mode is not enabled.
    const condition = {
      formula: "get('current_node.status_code') = 503",
      mode: 'simple',
      version: '0.1',
    }
    const wrapper = await mountForm({
      ...retryNode,
      retry_condition: condition,
    })

    const input = conditionInput(wrapper)
    expect(input.exists()).toBe(true)
    expect(input.props('enabledModes')).toEqual(['advanced'])
    expect(input.props('modelValue')).toEqual(condition)
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

  test('an edit of the condition is emitted as is', async () => {
    const wrapper = await mountForm(retryNode)
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
    await retriesInput(wrapper).setValue('3')

    expect(wrapper.emitted('values-changed')).toBeUndefined()
    expect(segments(wrapper)[1].classes()).toContain(
      'segment-control__button--active'
    )
    expect(conditionInput(wrapper).props('disabled')).toBe(true)
    expect(retriesInput(wrapper).element.disabled).toBe(true)
  })

  test('follows the node when another one is selected', async () => {
    const wrapper = await mountForm(retryNode)
    expect(conditionInput(wrapper).exists()).toBe(true)

    await wrapper.setProps({ node: { ...stopNode, id: 2 } })

    expect(segments(wrapper)[0].classes()).toContain(
      'segment-control__button--active'
    )
    expect(conditionInput(wrapper).exists()).toBe(false)
    expect(wrapper.emitted('values-changed')).toBeUndefined()
  })
})
