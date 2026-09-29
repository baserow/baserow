import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

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
