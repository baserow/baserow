import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'

import WorkflowNodeContext from '@baserow/modules/automation/components/workflow/WorkflowNodeContext'

const ContextStub = defineComponent({
  name: 'Context',
  emits: ['shown'],
  template: '<div><slot /></div>',
})

const WorkflowAddNodeMenuStub = defineComponent({
  name: 'WorkflowAddNodeMenu',
  methods: {
    focus() {
      this.$refs.search.focus()
    },
  },
  template: '<input ref="search" class="menu-search__input" />',
})

describe('WorkflowNodeContext', () => {
  test('focuses the search when the context opens', async () => {
    const wrapper = mount(WorkflowNodeContext, {
      attachTo: document.body,
      global: {
        stubs: {
          Context: ContextStub,
          WorkflowAddNodeMenu: WorkflowAddNodeMenuStub,
        },
      },
    })

    wrapper.findComponent(ContextStub).vm.$emit('shown')
    await nextTick()

    expect(document.activeElement).toBe(
      wrapper.find('.menu-search__input').element
    )

    wrapper.unmount()
  })
})
