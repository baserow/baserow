import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import ApplicationUntrustedContentAlert from '@baserow/modules/core/components/application/ApplicationUntrustedContentAlert'
import WorkflowGeneralSettings from '@baserow/modules/automation/components/settings/WorkflowGeneralSettings'
import WorkspaceService from '@baserow/modules/core/services/workspace'

vi.mock('@baserow/modules/core/services/workspace', () => ({
  default: vi.fn(),
}))

describe('WorkflowGeneralSettings', () => {
  test('normalizes loaded workspace members as user subjects', async () => {
    const members = [
      { user_id: 1, name: 'Ada', email: 'ada@example.com' },
      { user_id: 2, name: 'Grace', email: 'grace@example.com' },
    ]
    const fetchAllUsers = vi.fn().mockResolvedValue({ data: members })
    WorkspaceService.mockReturnValue({ fetchAllUsers })

    const wrapper = await mountSuspended(WorkflowGeneralSettings, {
      props: {
        automation: { id: 10, workspace: { id: 12 } },
        workflow: { id: 20 },
        defaultValues: { name: 'Workflow', notification_recipient_ids: [] },
      },
      global: {
        stubs: {
          FormGroup: { template: '<div><slot /></div>' },
          FormInput: true,
          Badge: true,
          Button: true,
          MemberAssignmentModal: {
            props: ['members'],
            template:
              '<div class="members">{{ JSON.stringify(members) }}</div>',
          },
        },
      },
    })
    await flushPromises()

    expect(fetchAllUsers).toHaveBeenCalledWith(12)
    expect(JSON.parse(wrapper.find('.members').text())).toEqual(
      members.map((member) => ({
        ...member,
        subject_type: 'auth.User',
      }))
    )
  })
})

test('trusts only the workflow shown in settings', async () => {
  WorkspaceService.mockReturnValue({
    fetchAllUsers: vi.fn().mockResolvedValue({ data: [] }),
  })
  const automation = { id: 10, workspace: { id: 12 } }
  const workflow = {
    id: 20,
    name: 'Code',
    notification_recipient_ids: [],
    untrusted_content: true,
  }
  const { $store } = useNuxtApp()
  const dispatch = vi.spyOn($store, 'dispatch').mockResolvedValue(undefined)
  const wrapper = await mountSuspended(WorkflowGeneralSettings, {
    props: { automation, workflow, defaultValues: workflow },
    global: { stubs: { MemberAssignmentModal: true } },
  })
  await flushPromises()
  const alert = wrapper.findComponent(ApplicationUntrustedContentAlert)
  expect(wrapper.findComponent({ name: 'Checkbox' }).exists()).toBe(false)
  expect(alert.html()).toMatchSnapshot()
  expect(dispatch).not.toHaveBeenCalledWith(
    'automationWorkflow/update',
    expect.anything()
  )
  await alert.props('trustContent')()
  expect(dispatch).toHaveBeenCalledWith('automationWorkflow/update', {
    automation,
    workflow,
    values: { untrusted_content: false },
  })
  wrapper.unmount()
  dispatch.mockRestore()
})

describe('WorkflowGeneralSettings description', () => {
  const mountSettings = async () => {
    WorkspaceService.mockReturnValue({
      fetchAllUsers: vi.fn().mockResolvedValue({ data: [] }),
    })
    const automation = { id: 10, workspace: { id: 12 } }
    const workflow = {
      id: 20,
      name: 'Orders',
      description: 'Before',
      notification_recipient_ids: [],
    }
    const { $store } = useNuxtApp()
    const dispatch = vi.spyOn($store, 'dispatch').mockResolvedValue(undefined)
    const wrapper = await mountSuspended(WorkflowGeneralSettings, {
      props: { automation, workflow, defaultValues: workflow },
      global: { stubs: { MemberAssignmentModal: true } },
    })
    await flushPromises()
    return { wrapper, dispatch, automation, workflow }
  }

  const waitForDebounce = () =>
    new Promise((resolve) => setTimeout(resolve, 400))

  test('saves a changed description', async () => {
    const { wrapper, dispatch, automation, workflow } = await mountSettings()

    const textarea = wrapper.find('textarea')
    expect(textarea.element.value).toBe('Before')
    await textarea.setValue('Sends the **weekly** report')
    await waitForDebounce()

    expect(dispatch).toHaveBeenCalledWith('automationWorkflow/update', {
      automation,
      workflow,
      values: expect.objectContaining({
        description: 'Sends the **weekly** report',
      }),
    })
    wrapper.unmount()
    dispatch.mockRestore()
  })

  test('does not save a description that is too long', async () => {
    const { wrapper, dispatch } = await mountSettings()

    await wrapper.find('textarea').setValue('a'.repeat(2001))
    await waitForDebounce()

    expect(dispatch).not.toHaveBeenCalledWith(
      'automationWorkflow/update',
      expect.anything()
    )
    wrapper.unmount()
    dispatch.mockRestore()
  })
})
