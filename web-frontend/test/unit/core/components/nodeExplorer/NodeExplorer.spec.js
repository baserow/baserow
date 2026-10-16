import { vi } from 'vitest'
import { nextTick } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import NodeExplorer from '@baserow/modules/core/components/nodeExplorer/NodeExplorer.vue'

const FormulaInputFieldStub = {
  props: { value: { type: String, default: '' } },
  template: '<code class="formula-input-field-stub">{{ value }}</code>',
}

const nodesHierarchy = [
  {
    name: 'Data',
    type: 'data',
    nodes: [
      {
        name: 'Data source',
        identifier: 'data_source',
        type: 'object',
        nodes: [
          {
            name: 'Projects',
            identifier: 'projects',
            type: 'object',
            nodes: [{ name: 'Name', identifier: 'field_1', type: 'string' }],
          },
        ],
      },
    ],
  },
  {
    name: 'Functions',
    type: 'function',
    nodes: [
      {
        name: 'Text',
        identifier: null,
        nodes: [
          { name: 'concat', type: 'function', identifier: null },
          { name: 'upper', type: 'function', identifier: null },
        ],
      },
    ],
  },
  {
    name: 'Operators',
    type: 'operator',
    nodes: [
      {
        name: 'Comparison',
        identifier: null,
        nodes: [
          {
            name: 'less_than',
            type: 'operator',
            identifier: null,
            signature: { operator: '<' },
          },
        ],
      },
    ],
  },
]

describe('NodeExplorer reveal', () => {
  let testApp = null
  let scrollIntoView = null

  beforeEach(() => {
    testApp = new TestApp()
    scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    // jsdom doesn't lay out, so make every row count as visible.
    vi.spyOn(Element.prototype, 'getClientRects').mockReturnValue([{}])
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    delete Element.prototype.scrollIntoView
    await testApp.afterEach()
  })

  async function mountExplorer(props = {}) {
    const wrapper = await testApp.mount(NodeExplorer, {
      props: { nodesHierarchy, ...props },
      global: {
        provide: { nodesHierarchy: [] },
        stubs: { FormulaInputField: FormulaInputFieldStub },
      },
    })
    await settle()
    return wrapper
  }

  async function settle() {
    for (let i = 0; i < 3; i++) {
      await nextTick()
    }
  }

  function activeTabTitle(wrapper) {
    return wrapper.find('.tabs__item--active').text()
  }

  function scrolledPath() {
    return scrollIntoView.mock.contexts.at(-1)?.dataset.nodePath
  }

  test('opens the functions tab and scrolls to a revealed function', async () => {
    const wrapper = await mountExplorer()
    expect(activeTabTitle(wrapper)).toBe('Data')

    await wrapper.setProps({ revealNode: { type: 'function', name: 'upper' } })
    await settle()

    expect(activeTabTitle(wrapper)).toBe('Functions')
    expect(scrolledPath()).toBe('Text.upper')
    expect(
      wrapper
        .find('[data-node-path="Text.upper"]')
        .classes('node-explorer-content__content--revealed')
    ).toBe(true)
  })

  test('opens the operators tab and scrolls to a revealed operator', async () => {
    const wrapper = await mountExplorer()

    await wrapper.setProps({ revealNode: { type: 'operator', name: '<' } })
    await settle()

    expect(activeTabTitle(wrapper)).toBe('Operators')
    expect(scrolledPath()).toBe('Comparison.less_than')
  })

  test('reveals a node passed when the explorer mounts', async () => {
    const wrapper = await mountExplorer({
      revealNode: { type: 'operator', name: '<' },
    })

    expect(activeTabTitle(wrapper)).toBe('Operators')
    expect(scrolledPath()).toBe('Comparison.less_than')
  })

  test('opens the data tab and expands the parents of a revealed data node', async () => {
    const wrapper = await mountExplorer({
      revealNode: { type: 'function', name: 'concat' },
    })
    expect(activeTabTitle(wrapper)).toBe('Functions')

    await wrapper.setProps({
      revealNode: { type: 'data', path: 'data_source.projects.field_1' },
    })
    await settle()

    expect(activeTabTitle(wrapper)).toBe('Data')
    expect(scrolledPath()).toBe('data_source.projects.field_1')
  })

  test('clears the search without unselecting the revealed data node', async () => {
    const wrapper = await mountExplorer({
      revealNode: { type: 'function', name: 'concat' },
    })
    wrapper.vm.search = 'upp'
    await settle()
    const unselectedCount = wrapper.emitted('node-unselected').length

    await wrapper.setProps({
      revealNode: { type: 'data', path: 'data_source.projects.field_1' },
    })
    await settle()

    expect(wrapper.vm.search).toBe(null)
    expect(wrapper.emitted('node-unselected')).toHaveLength(unselectedCount)
  })

  test('ignores a node the explorer does not have', async () => {
    const wrapper = await mountExplorer()

    await wrapper.setProps({ revealNode: { type: 'function', name: 'nope' } })
    await settle()

    expect(activeTabTitle(wrapper)).toBe('Data')
    expect(scrollIntoView).not.toHaveBeenCalled()
  })

  test('only reveals data nodes in simple mode', async () => {
    const wrapper = await mountExplorer({ mode: 'simple' })

    await wrapper.setProps({ revealNode: { type: 'function', name: 'upper' } })
    await settle()

    expect(scrollIntoView).not.toHaveBeenCalled()

    await wrapper.setProps({
      revealNode: { type: 'data', path: 'data_source.projects' },
    })
    await settle()

    expect(scrolledPath()).toBe('data_source.projects')
  })
})
