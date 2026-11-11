import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'

import WorkflowNodeContext from '@baserow/modules/automation/components/workflow/WorkflowNodeContext'

const hide = vi.fn()

const ContextStub = defineComponent({
  name: 'Context',
  emits: ['shown'],
  methods: {
    hide() {
      hide()
    },
  },
  template: '<div><slot /></div>',
})

const WorkflowAddNodeMenuStub = defineComponent({
  name: 'WorkflowAddNodeMenu',
  emits: ['change', 'recipe', 'close'],
  methods: {
    focus() {
      this.$refs.search.focus()
    },
  },
  template: '<input ref="search" class="menu-search__input" />',
})

const mountContext = (options = {}) =>
  mount(WorkflowNodeContext, {
    ...options,
    global: {
      stubs: {
        Context: ContextStub,
        WorkflowAddNodeMenu: WorkflowAddNodeMenuStub,
      },
    },
  })

describe('WorkflowNodeContext', () => {
  beforeEach(() => {
    hide.mockClear()
  })

  test('focuses the search when the context opens', async () => {
    const wrapper = mountContext({ attachTo: document.body })

    wrapper.findComponent(ContextStub).vm.$emit('shown')
    await nextTick()

    expect(document.activeElement).toBe(
      wrapper.find('.menu-search__input').element
    )

    wrapper.unmount()
  })

  test('hides and re-emits the picked node type', async () => {
    const wrapper = mountContext()

    wrapper
      .findComponent(WorkflowAddNodeMenuStub)
      .vm.$emit('change', 'iterator')
    await nextTick()

    expect(hide).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('change')).toEqual([['iterator']])
    expect(wrapper.emitted('recipe')).toBeUndefined()
  })

  test('hides and re-emits the picked recipe', async () => {
    const wrapper = mountContext()

    wrapper
      .findComponent(WorkflowAddNodeMenuStub)
      .vm.$emit('recipe', 'while_loop')
    await nextTick()

    expect(hide).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('recipe')).toEqual([['while_loop']])
    expect(wrapper.emitted('change')).toBeUndefined()
  })
})
