import { mountSuspended } from '@nuxt/test-utils/runtime'
import WorkflowAction from '@baserow/modules/builder/components/event/WorkflowAction.vue'

describe('WorkflowAction', () => {
  const mountComponent = ({ workflowActionType, workflowAction }) => {
    const builder = { id: 1 }
    const page = { id: 1 }
    const workspace = { id: 1 }
    const mode = 'editing'
    const element = { id: 1 }

    return mountSuspended(WorkflowAction, {
      props: {
        availableWorkflowActionTypes: [workflowActionType],
        workflowAction,
        element,
        expanded: true,
      },
      global: {
        provide: {
          builder,
          elementPage: page,
          mode,
          workspace,
          applicationContext: { builder, page, mode, workspace },
        },
        stubs: {
          SidebarExpandable: {
            template: `
              <section>
                <slot name="title" />
                <slot />
                <slot name="footer" />
              </section>
            `,
          },
          SampleDataViewer: {
            name: 'SampleDataViewer',
            props: ['sampleData', 'isError', 'modalTitle', 'modalSubtitle'],
            template: '<div class="sample-data-viewer" />',
          },
          ButtonText: {
            template: '<button><slot /></button>',
          },
        },
      },
    })
  }

  test('shows list service sample data without throwing', async () => {
    const workflowActionType = {
      form: {
        template: '<form />',
        methods: {
          isFormValid() {
            return true
          },
        },
      },
      icon: 'iconoir-page',
      label: 'Read xls file',
      returnsList: true,
      getType() {
        return 'xls_file_reader'
      },
      getErrorMessage() {
        return null
      },
    }
    const results = [{ id: 1, name: 'First row' }]

    const wrapper = await mountComponent({
      workflowActionType,
      workflowAction: {
        id: 1,
        type: 'xls_file_reader',
        service: {
          sample_data: {
            data: {
              results,
            },
          },
        },
      },
    })

    expect(
      wrapper.findComponent({ name: 'SampleDataViewer' }).props()
    ).toMatchObject({
      sampleData: results,
      isError: false,
    })
  })
})
