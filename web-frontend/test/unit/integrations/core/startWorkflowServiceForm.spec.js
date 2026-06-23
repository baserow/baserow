import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import CoreStartWorkflowServiceForm from '@baserow/modules/integrations/core/components/services/CoreStartWorkflowServiceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  template: '<div><slot /></div>',
})

const DropdownStub = defineComponent({
  name: 'Dropdown',
  props: {
    modelValue: {
      type: Number,
      required: false,
      default: null,
    },
  },
  emits: ['update:modelValue'],
  template: '<div><slot /></div>',
})

const DropdownItemStub = defineComponent({
  name: 'DropdownItem',
  props: {
    name: {
      type: String,
      required: true,
    },
    value: {
      type: Number,
      required: true,
    },
  },
  template: '<div />',
})

const DropdownSectionStub = defineComponent({
  name: 'DropdownSection',
  props: {
    title: {
      type: String,
      required: true,
    },
  },
  template: '<div><slot /></div>',
})

const workspace = { id: 1 }
const automations = [
  {
    id: 1,
    name: 'Current automation',
    type: 'automation',
    order: 1,
    workspace,
    workflows: [
      {
        id: 101,
        name: 'Current workflow',
        order: 1,
        immediate_dispatch: true,
      },
    ],
  },
  {
    id: 2,
    name: 'Other automation',
    type: 'automation',
    order: 2,
    workspace,
    workflows: [
      {
        id: 202,
        name: 'Other first workflow',
        order: 1,
        immediate_dispatch: true,
      },
      {
        id: 201,
        name: 'Saved workflow',
        order: 2,
        immediate_dispatch: true,
      },
    ],
  },
]

async function mountComponent(defaultValues = { workflow_id: 201 }) {
  return await mountSuspended(CoreStartWorkflowServiceForm, {
    props: {
      defaultValues,
    },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        Dropdown: DropdownStub,
        DropdownSection: DropdownSectionStub,
        DropdownItem: DropdownItemStub,
      },
      mocks: {
        $t: (key) => key,
        $store: {
          getters: {
            'workspace/getSelected': workspace,
            'application/getAllOfWorkspace': () => automations,
            'automationWorkflow/getOrderedWorkflows': (automation) =>
              [...automation.workflows].sort((a, b) => a.order - b.order),
          },
        },
      },
    },
  })
}

describe('CoreStartWorkflowServiceForm', () => {
  test('keeps the saved workflow selected on mount', async () => {
    const wrapper = await mountComponent()
    await flushPromises()

    expect(wrapper.vm.values.workflow_id).toBe(201)
  })

  test('does not automatically select a workflow without a saved value', async () => {
    const wrapper = await mountComponent({ workflow_id: null })
    await flushPromises()

    expect(wrapper.vm.values.workflow_id).toBe(null)
  })

  test('groups workflows by automation', async () => {
    const wrapper = await mountComponent()
    await flushPromises()

    const sectionTitles = wrapper
      .findAllComponents({ name: 'DropdownSection' })
      .map((section) => section.props('title'))
    const workflowNames = wrapper
      .findAllComponents({ name: 'DropdownItem' })
      .map((item) => item.props('name'))

    expect(sectionTitles).toEqual(['Current automation', 'Other automation'])
    expect(workflowNames).toEqual([
      'Current workflow',
      'Other first workflow',
      'Saved workflow',
    ])
  })
})
