import { vi } from 'vitest'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import NodeHelpTooltip from '@baserow/modules/core/components/nodeExplorer/NodeHelpTooltip.vue'

// Each example is normally rendered as a read-only tiptap editor. That is
// irrelevant here, so render the formula as plain text instead.
const FormulaInputFieldStub = {
  props: { value: { type: String, default: '' } },
  template: '<code class="formula-input-field-stub">{{ value }}</code>',
}

const upperNode = {
  name: 'upper',
  type: 'function',
  description: 'Converts a string to uppercase.',
  icon: 'iconoir-text',
  examples: [
    { formula: "upper('hello')", result: "'HELLO'" },
    { formula: "upper(concat('a', 'b'))", result: "'AB'" },
    { formula: "upper('MiXeD')", result: "'MIXED'" },
  ],
}

describe('NodeHelpTooltip', () => {
  let testApp = null
  let target = null

  beforeEach(() => {
    testApp = new TestApp()
    target = document.createElement('div')
    document.body.appendChild(target)
  })

  afterEach(async () => {
    target.remove()
    await testApp.afterEach()
  })

  async function mountTooltip(props = {}) {
    const wrapper = await testApp.mount(NodeHelpTooltip, {
      props: { node: upperNode, ...props },
      global: {
        provide: { nodesHierarchy: [] },
        stubs: { FormulaInputField: FormulaInputFieldStub },
      },
    })
    // The Context only renders its content once shown, which is what the node
    // explorer does when a node is hovered.
    wrapper.vm.show(target)
    await flushPromises()
    return wrapper
  }

  test('renders every example of the node', async () => {
    const wrapper = await mountTooltip()

    expect(wrapper.find('.node-help-tooltip__title').text()).toBe('upper')
    expect(wrapper.find('.node-help-tooltip__description').text()).toBe(
      'Converts a string to uppercase.'
    )
    expect(wrapper.find('.node-help-tooltip .control__label').text()).toBe(
      'nodeHelpTooltip.exampleLabel - 3'
    )

    const examples = wrapper.findAll('.node-help-tooltip__example')
    expect(
      examples.map((example) =>
        example.find('.formula-input-field-stub').text()
      )
    ).toEqual(["upper('hello')", "upper(concat('a', 'b'))", "upper('MiXeD')"])
    expect(
      examples.every((example) =>
        example.find('.control__helper-text').exists()
      )
    ).toBe(true)
  })

  test('renders no example section for a node without examples', async () => {
    const wrapper = await mountTooltip({
      node: { ...upperNode, examples: null },
    })

    expect(wrapper.find('.node-help-tooltip__description').exists()).toBe(true)
    expect(wrapper.find('.node-help-tooltip__examples').exists()).toBe(false)
    expect(wrapper.find('.node-help-tooltip__examples-hint').exists()).toBe(
      false
    )
  })

  test('renders no result line for an example without one', async () => {
    const wrapper = await mountTooltip({
      node: {
        ...upperNode,
        examples: [{ formula: 'get()', result: '' }],
      },
    })

    const examples = wrapper.findAll('.node-help-tooltip__example')
    expect(examples).toHaveLength(1)
    expect(examples[0].find('.formula-input-field-stub').text()).toBe('get()')
    expect(examples[0].find('.control__helper-text').exists()).toBe(false)
  })

  test('renders no description for a node without one', async () => {
    const wrapper = await mountTooltip({
      node: { ...upperNode, description: null },
    })

    expect(wrapper.find('.node-help-tooltip__title').text()).toBe('upper')
    expect(wrapper.find('.node-help-tooltip__description').exists()).toBe(false)
    expect(wrapper.findAll('.node-help-tooltip__example')).toHaveLength(3)
  })

  test('is display-only by default', async () => {
    const wrapper = await mountTooltip()
    const documentClick = vi.fn()
    document.addEventListener('click', documentClick)

    expect(
      wrapper.find('.node-help-tooltip__examples--clickable').exists()
    ).toBe(false)
    expect(
      wrapper.find('.node-help-tooltip__example--clickable').exists()
    ).toBe(false)
    expect(wrapper.find('.node-help-tooltip__examples-hint').exists()).toBe(
      false
    )

    await wrapper.findAll('.node-help-tooltip__example')[1].trigger('click')

    expect(wrapper.emitted('example-click')).toBeUndefined()
    // Nothing intercepts the click, so it bubbles up to the document.
    expect(documentClick).toHaveBeenCalledTimes(1)
    document.removeEventListener('click', documentClick)
  })

  test('emits the clicked example when examples are clickable', async () => {
    const wrapper = await mountTooltip({ clickableExamples: true })

    expect(
      wrapper.find('.node-help-tooltip__examples--clickable').exists()
    ).toBe(true)
    expect(
      wrapper.findAll('.node-help-tooltip__example--clickable')
    ).toHaveLength(3)
    expect(wrapper.find('.node-help-tooltip__examples-hint').text()).toBe(
      'nodeHelpTooltip.clickToInsert'
    )

    await wrapper.findAll('.node-help-tooltip__example')[1].trigger('click')

    expect(wrapper.emitted('example-click')).toEqual([[upperNode.examples[1]]])
  })

  test('keeps example clicks from blurring the editor or reaching the document', async () => {
    const wrapper = await mountTooltip({ clickableExamples: true })
    const documentClick = vi.fn()
    document.addEventListener('click', documentClick)
    const example = wrapper.find('.node-help-tooltip__example')

    // The tooltip lives outside the formula editor, so a mousedown would blur
    // the editor and close the explorer before the click lands.
    const mousedown = new MouseEvent('mousedown', {
      bubbles: true,
      cancelable: true,
    })
    example.element.dispatchEvent(mousedown)
    expect(mousedown.defaultPrevented).toBe(true)

    // The click must not reach the document-level click-outside handlers.
    await example.trigger('click')
    expect(documentClick).not.toHaveBeenCalled()
    expect(wrapper.emitted('example-click')).toHaveLength(1)
    document.removeEventListener('click', documentClick)
  })

  test('reports the mouse entering and leaving it', async () => {
    const wrapper = await mountTooltip()
    const tooltip = wrapper.find('.node-help-tooltip')

    await tooltip.trigger('mouseenter')
    expect(wrapper.emitted('mouseenter')).toHaveLength(1)
    expect(wrapper.emitted('mouseleave')).toBeUndefined()

    await tooltip.trigger('mouseleave')
    expect(wrapper.emitted('mouseleave')).toHaveLength(1)
  })
})
