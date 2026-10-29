import { mountSuspended } from '@nuxt/test-utils/runtime'
import { nextTick, reactive, ref } from 'vue'
import PageHeader from '@baserow/modules/builder/components/page/header/PageHeader'
import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'

describe.each([
  ['builder', PageHeader],
  ['automation', AutomationHeader],
])('%s untrusted content header alert', (type, header) => {
  test('stays visible until content is trusted and returns when blocked again', async () => {
    const application = reactive({
      id: 1,
      type,
      workspace: { id: 1 },
      untrusted_content: true,
    })
    const workflow = ref({ id: 1, nodes: [], untrusted_content: true })
    const owner = type === 'builder' ? application : workflow.value
    const wrapper = await mountSuspended(header, {
      props: type === 'automation' ? { automation: application } : {},
      global: {
        provide: {
          builder: application,
          workflow,
          workspace: ref(application.workspace),
          isDev: false,
        },
        mocks: {
          $hasPermission: () => false,
          $store: { getters: { 'page/getDeviceTypeSelected': 'desktop' } },
        },
        stubs: {
          PageHeaderMenuItems: true,
          DeviceSelector: true,
          PageActions: true,
          WorkflowSettingsModal: true,
        },
      },
    })

    expect(wrapper.find('[role="alert"]').html()).toMatchSnapshot()
    expect(wrapper.find('.alert__close').exists()).toBe(false)

    owner.untrusted_content = false
    await nextTick()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)

    owner.untrusted_content = true
    await nextTick()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    if (type === 'automation') {
      workflow.value = { id: 2, nodes: [], untrusted_content: false }
      await nextTick()
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
      workflow.value = owner
      await nextTick()
      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    }
    wrapper.unmount()
  })
})

describe.each([
  ['builder', PageHeader],
  ['automation', AutomationHeader],
])('%s report confirmation', (type, header) => {
  test('opens the report link and trusts exactly its content owner', async () => {
    const application = reactive({
      id: 1,
      workspace: { id: 1 },
      untrusted_content: true,
    })
    const workflow = ref({ id: 2, nodes: [], untrusted_content: true })
    const owner = type === 'builder' ? application : workflow.value
    owner.import_report = [{ type: 'custom_js' }]
    const dispatch = vi.fn().mockImplementation(async () => {
      owner.untrusted_content = false
    })
    const store = {
      dispatch,
      getters: { 'page/getDeviceTypeSelected': 'desktop' },
    }
    const wrapper = await mountSuspended(header, {
      props: type === 'automation' ? { automation: application } : {},
      global: {
        provide: {
          store,
          builder: application,
          workflow,
          workspace: ref(application.workspace),
          isDev: false,
        },
        mocks: {
          $store: store,
          $hasPermission: (operation) =>
            operation ===
            (type === 'builder'
              ? 'application.update'
              : 'automation.workflow.update'),
        },
        stubs: {
          teleport: true,
          PageHeaderMenuItems: true,
          DeviceSelector: true,
          PageActions: true,
          WorkflowSettingsModal: true,
        },
      },
    })
    await wrapper.find('[role="alert"] a').trigger('click')
    await nextTick()
    expect(wrapper.find('.untrusted-content-report').text()).toContain(
      'untrustedContentReviewModal.typeJs'
    )
    expect(dispatch).not.toHaveBeenCalled()
    const trust = wrapper
      .findAllComponents({ name: 'Button' })
      .find((button) => button.text() === 'untrustedContentReviewModal.trust')
    await trust.trigger('click')
    await nextTick()
    expect(dispatch).toHaveBeenCalledWith(
      type === 'builder' ? 'application/update' : 'automationWorkflow/update',
      type === 'builder'
        ? { application, values: { untrusted_content: false } }
        : {
            automation: application,
            workflow: workflow.value,
            values: { untrusted_content: false },
          }
    )
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
