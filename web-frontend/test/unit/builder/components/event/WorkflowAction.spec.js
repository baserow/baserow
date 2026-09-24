import { vi } from 'vitest'
import { reactive } from 'vue'
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

  // A form stub whose `reset()` re-reads the current `defaultValues` (like the real
  // form mixin), and records that it was called. This lets us observe that the side
  // panel calls `reset()` (rather than remounting) when a realtime change arrives.
  const makeResetProbe = () => {
    const resetSpy = vi.fn()
    const workflowActionType = {
      form: {
        name: 'ActionFormStub',
        props: ['defaultValues', 'workflowAction'],
        data() {
          return { snapshot: this.defaultValues?.value }
        },
        methods: {
          isFormValid() {
            return true
          },
          reset() {
            resetSpy()
            this.snapshot = this.defaultValues?.value
          },
        },
        template: '<div class="form-value">{{ snapshot }}</div>',
      },
      getType() {
        return 'probe'
      },
      getErrorMessage() {
        return null
      },
    }
    return { workflowActionType, resetSpy }
  }

  test('resets the form when the action changes via realtime (undo/redo)', async () => {
    // Mirrors the real app: the realtime `forceUpdate` mutates the same store
    // object in place (bumping `_.realtimeVersion`), rather than replacing it.
    const { workflowActionType, resetSpy } = makeResetProbe()
    const workflowAction = reactive({
      id: 1,
      type: 'probe',
      value: 'a',
      _: { viaRealtime: false, realtimeVersion: 0 },
    })
    const wrapper = await mountComponent({ workflowActionType, workflowAction })
    expect(wrapper.find('.form-value').text()).toBe('a')

    // Apply an undo/redo as the store mutation would: in place, same object.
    workflowAction.value = 'b'
    workflowAction._.viaRealtime = true
    workflowAction._.realtimeVersion = 1
    await wrapper.vm.$nextTick()

    // The panel called reset(), so the form re-read the new default value.
    expect(resetSpy).toHaveBeenCalled()
    expect(wrapper.find('.form-value').text()).toBe('b')
  })

  test('does not reset the form on a local (non-realtime) update', async () => {
    const { workflowActionType, resetSpy } = makeResetProbe()
    const workflowAction = reactive({
      id: 1,
      type: 'probe',
      value: 'a',
      _: { viaRealtime: false, realtimeVersion: 0 },
    })
    const wrapper = await mountComponent({ workflowActionType, workflowAction })
    expect(wrapper.find('.form-value').text()).toBe('a')

    // A local edit does not change realtimeVersion, so the form is not reset.
    workflowAction.value = 'b'
    await wrapper.vm.$nextTick()

    expect(resetSpy).not.toHaveBeenCalled()
    expect(wrapper.find('.form-value').text()).toBe('a')
  })

  test('does not reset when viaRealtime is stale but the version has not advanced', async () => {
    // Guards against relying on `viaRealtime` alone: it stays set until the next
    // local edit, so a reset must only happen when the version actually advances.
    const { workflowActionType, resetSpy } = makeResetProbe()
    const workflowAction = reactive({
      id: 1,
      type: 'probe',
      value: 'a',
      _: { viaRealtime: true, realtimeVersion: 3 },
    })
    const wrapper = await mountComponent({ workflowActionType, workflowAction })

    // `viaRealtime` flips to true again, but the version is unchanged.
    workflowAction._.viaRealtime = true
    await wrapper.vm.$nextTick()

    expect(resetSpy).not.toHaveBeenCalled()
  })
})
