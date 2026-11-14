import { vi } from 'vitest'
import { nextTick } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import NodeExplorerContent from '@baserow/modules/core/components/nodeExplorer/NodeExplorerContent.vue'

// Tooltip examples are normally read-only tiptap editors, which are not
// relevant to the hover behaviour tested here.
const FormulaInputFieldStub = {
  props: { value: { type: String, default: '' } },
  template: '<code class="formula-input-field-stub">{{ value }}</code>',
}

// Must match the delays used by `NodeExplorerContent`.
const SHOW_DELAY = 300
const HIDE_DELAY = 250

function functionNode(overrides = {}) {
  return {
    name: 'upper',
    type: 'function',
    description: 'Converts a string to uppercase.',
    icon: 'iconoir-text',
    identifier: null,
    signature: null,
    highlightingColor: 'blue',
    examples: [
      { formula: "upper('hello')", result: "'HELLO'" },
      { formula: "upper('MiXeD')", result: "'MIXED'" },
    ],
    ...overrides,
  }
}

describe('NodeExplorerContent help tooltip', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.useRealTimers()
    await testApp.afterEach()
  })

  async function mountContent(node, props = {}) {
    const wrapper = await testApp.mount(NodeExplorerContent, {
      props: {
        node,
        depth: 1,
        path: node.name,
        searchPath: node.name,
        openNodes: new Set(),
        ...props,
      },
      global: {
        provide: { getFormulaMode: () => 'advanced', nodesHierarchy: [] },
        stubs: { FormulaInputField: FormulaInputFieldStub },
      },
    })
    // Only the hover timers must be fake; mounting itself runs on real ones.
    vi.useFakeTimers()
    return wrapper
  }

  /**
   * Lets the tooltip Context finish showing/hiding: `show()` awaits a tick
   * before positioning and the class change needs another render.
   */
  async function settle() {
    for (let i = 0; i < 3; i++) {
      await nextTick()
    }
  }

  function tooltipVisible(wrapper) {
    const context = wrapper.find('.node-help-tooltip-context')
    return context.exists() && !context.classes('visibility-hidden')
  }

  async function hoverRow(wrapper, index = 0) {
    await wrapper
      .findAll('.node-explorer-content__content')
      [index].trigger('mouseenter')
    vi.advanceTimersByTime(SHOW_DELAY)
    await settle()
  }

  test('shows the tooltip after hovering a function node for a moment', async () => {
    const wrapper = await mountContent(functionNode())
    const row = wrapper.find('.node-explorer-content__content')

    await row.trigger('mouseenter')
    vi.advanceTimersByTime(SHOW_DELAY - 1)
    await settle()
    expect(tooltipVisible(wrapper)).toBe(false)

    vi.advanceTimersByTime(1)
    await settle()
    expect(tooltipVisible(wrapper)).toBe(true)
    expect(wrapper.findAll('.node-help-tooltip__example')).toHaveLength(2)
    expect(
      wrapper.find('.node-help-tooltip__examples--clickable').exists()
    ).toBe(true)
  })

  test('shows a description-only tooltip for a node without examples', async () => {
    const wrapper = await mountContent(functionNode({ examples: null }))

    await hoverRow(wrapper)

    expect(tooltipVisible(wrapper)).toBe(true)
    expect(wrapper.find('.node-help-tooltip__description').text()).toBe(
      'Converts a string to uppercase.'
    )
    expect(wrapper.find('.node-help-tooltip__examples').exists()).toBe(false)
  })

  test('does not show a tooltip for a node without description or examples', async () => {
    const wrapper = await mountContent(
      functionNode({ examples: null, description: null })
    )

    await hoverRow(wrapper)

    expect(tooltipVisible(wrapper)).toBe(false)
  })

  test('cancels a pending tooltip when the mouse leaves early', async () => {
    const wrapper = await mountContent(functionNode())
    const row = wrapper.find('.node-explorer-content__content')

    await row.trigger('mouseenter')
    vi.advanceTimersByTime(SHOW_DELAY / 2)
    await row.trigger('mouseleave')
    vi.advanceTimersByTime(SHOW_DELAY)
    await settle()

    expect(tooltipVisible(wrapper)).toBe(false)
  })

  test('hides the tooltip with a delay after leaving the node', async () => {
    const wrapper = await mountContent(functionNode())
    await hoverRow(wrapper)

    await wrapper.find('.node-explorer-content__content').trigger('mouseleave')
    vi.advanceTimersByTime(HIDE_DELAY - 1)
    await settle()
    expect(tooltipVisible(wrapper)).toBe(true)

    vi.advanceTimersByTime(1)
    await settle()
    expect(tooltipVisible(wrapper)).toBe(false)
  })

  test('keeps the tooltip open while the mouse is inside it', async () => {
    const wrapper = await mountContent(functionNode())
    await hoverRow(wrapper)
    const tooltip = wrapper.find('.node-help-tooltip')

    await wrapper.find('.node-explorer-content__content').trigger('mouseleave')
    vi.advanceTimersByTime(HIDE_DELAY / 2)
    await tooltip.trigger('mouseenter')
    vi.advanceTimersByTime(HIDE_DELAY * 2)
    await settle()
    expect(tooltipVisible(wrapper)).toBe(true)

    await tooltip.trigger('mouseleave')
    vi.advanceTimersByTime(HIDE_DELAY)
    await settle()
    expect(tooltipVisible(wrapper)).toBe(false)
  })

  test('re-emits a clicked example and hides the tooltip', async () => {
    const node = functionNode()
    const wrapper = await mountContent(node)
    await hoverRow(wrapper)

    await wrapper.findAll('.node-help-tooltip__example')[1].trigger('click')
    await settle()

    expect(wrapper.emitted('example-click')).toEqual([[node.examples[1]]])
    expect(tooltipVisible(wrapper)).toBe(false)
  })

  test('forwards example clicks from nested nodes', async () => {
    const child = functionNode()
    const category = {
      name: 'Text',
      description: null,
      examples: null,
      icon: null,
      identifier: null,
      nodes: [child],
    }
    const wrapper = await mountContent(category, {
      depth: 0,
      path: null,
      searchPath: '',
    })

    // Row 0 is the category itself, row 1 its child function.
    await hoverRow(wrapper, 1)
    await wrapper.find('.node-help-tooltip__example').trigger('click')

    expect(wrapper.emitted('example-click')).toEqual([[child.examples[0]]])
  })
})

describe('NodeExplorerContent sample values', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const values = {
    'previous_node.1.name': 'Acme Ltd',
    'previous_node.1.note': '',
    'previous_node.1.tags': ['a', 'b'],
    'previous_node.1.owner': { id: 1, name: 'Ada' },
  }

  const dataNode = (identifier, overrides = {}) => ({
    name: identifier,
    identifier,
    type: 'string',
    icon: 'iconoir-text',
    ...overrides,
  })

  function mountContent(node, props = {}) {
    return testApp.mount(NodeExplorerContent, {
      props: {
        node,
        depth: 2,
        path: `previous_node.1.${node.identifier}`,
        searchPath: `previous_node.1.${node.identifier}`,
        openNodes: new Set(),
        getValue: (path) => values[path],
        ...props,
      },
      global: {
        provide: { getFormulaMode: () => 'simple', nodesHierarchy: [] },
        stubs: { FormulaInputField: FormulaInputFieldStub },
      },
    })
  }

  const valueOf = (wrapper) => wrapper.find('.node-explorer-content__value')

  test('shows the value next to the name', async () => {
    const wrapper = await mountContent(dataNode('name'))

    expect(valueOf(wrapper).text()).toBe('Acme Ltd')
    expect(valueOf(wrapper).attributes('title')).toBe('Acme Ltd')
    // The value is guaranteed its own length, so a long name can't hide it.
    expect(valueOf(wrapper).attributes('style')).toContain(
      '--node-explorer-content-value-length: 9'
    )
    expect(valueOf(wrapper).classes()).not.toContain(
      'node-explorer-content__value--muted'
    )
  })

  test('shows a muted placeholder for an empty value', async () => {
    const wrapper = await mountContent(dataNode('note'))

    expect(valueOf(wrapper).text()).toBe('dataExplorerNode.emptyValue')
    expect(valueOf(wrapper).classes()).toContain(
      'node-explorer-content__value--muted'
    )
  })

  test('summarises lists and objects', async () => {
    const list = await mountContent(dataNode('tags', { type: 'array' }))
    const object = await mountContent(dataNode('owner', { type: 'object' }))

    expect(valueOf(list).text()).toContain('dataExplorerNode.itemCount')
    expect(valueOf(object).text()).toContain('dataExplorerNode.fieldCount')
  })

  test('shows nothing when the value is unknown', async () => {
    const wrapper = await mountContent(dataNode('unknown'))

    expect(valueOf(wrapper).exists()).toBe(false)
  })

  test('shows nothing when no values are provided', async () => {
    const wrapper = await mountContent(dataNode('name'), { getValue: null })

    expect(valueOf(wrapper).exists()).toBe(false)
    expect(wrapper.find('.node-explorer-content__name').classes()).toEqual([
      'node-explorer-content__name',
    ])
  })

  test('passes the values down to its children', async () => {
    const parent = dataNode('1', {
      type: 'object',
      nodes: [dataNode('name'), dataNode('unknown')],
    })
    const wrapper = await mountContent(parent, {
      depth: 1,
      path: 'previous_node.1',
      searchPath: 'previous_node.1',
      openNodes: new Set(['previous_node.1']),
    })

    expect(
      wrapper.findAll('.node-explorer-content__value').map((el) => el.text())
    ).toEqual(['Acme Ltd'])
  })

  test('shows the hint of a node', async () => {
    const wrapper = await mountContent(
      dataNode('1', { hint: 'Test this step to see its values' }),
      { depth: 1, path: 'previous_node.1', searchPath: 'previous_node.1' }
    )

    expect(wrapper.find('.node-explorer-content__hint').text()).toBe(
      'Test this step to see its values'
    )
  })
})
