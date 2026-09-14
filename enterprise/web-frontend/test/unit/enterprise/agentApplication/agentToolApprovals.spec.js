import { mountSuspended } from '@nuxt/test-utils/runtime'

import AgentToolApprovals from '@baserow_enterprise/components/agentApplication/AgentToolApprovals'

const approval = (id, values = {}) => ({
  id,
  tool_call_id: `call-${id}`,
  tool_name: 'create_rows_in_table_5',
  tool_args: { table_id: 5, rows: [{ Name: 'Acme' }] },
  status: 'pending',
  reason: '',
  ...values,
})

async function mount(approvals, props = {}) {
  return await mountSuspended(AgentToolApprovals, {
    props: {
      approvals,
      canDecide: true,
      canChangeTools: true,
      agentName: 'Outreach',
      toolLabel: (name) => `label:${name}`,
      ...props,
    },
    global: {
      stubs: { AgentRejectApprovalModal: true },
    },
  })
}

describe('AgentToolApprovals', () => {
  test('renders the pending header, labels and args summary', async () => {
    const wrapper = await mount([approval(1), approval(2)])
    // Translations are not loaded in unit tests, so the keys render.
    expect(wrapper.text()).toContain('agentToolApprovals.asksForApproval')
    expect(wrapper.text()).toContain('label:create_rows_in_table_5')
    expect(wrapper.text()).toContain('table_id: 5')
    expect(wrapper.find('.agent-tool-approvals__details-id').text()).toBe(
      'create_rows_in_table_5'
    )
  })

  test('approve all emits every pending decision with the ask-again flag', async () => {
    const wrapper = await mount([
      approval(1),
      approval(2, { status: 'approved' }),
      approval(3),
    ])
    await wrapper
      .find('.agent-tool-approvals__header-actions input')
      .setValue(true)
    const buttons = wrapper.findAll(
      '.agent-tool-approvals__header-actions button'
    )
    await buttons.at(-1).trigger('click')

    expect(wrapper.emitted('decide')).toHaveLength(1)
    expect(wrapper.emitted('decide')[0][0]).toEqual({
      decisions: [
        { id: 1, approved: true },
        { id: 3, approved: true },
      ],
      dontAskAgain: true,
    })
  })

  test('shows the reviewed summary once nothing is pending', async () => {
    const wrapper = await mount([
      approval(1, { status: 'approved' }),
      approval(2, { status: 'rejected', reason: 'Not now' }),
    ])
    expect(wrapper.text()).toContain('agentToolApprovals.reviewedByYou')
    expect(wrapper.find('.agent-tool-approvals__header-summary').text()).toBe(
      'agentToolApprovals.approvedCount - 1 · agentToolApprovals.rejectedCount - 1'
    )
    expect(wrapper.text()).toContain('agentToolApprovals.rejected · Not now')
    expect(wrapper.find('.agent-tool-approvals__header-actions').exists()).toBe(
      false
    )
  })

  test('a single rejection with a reason emits that decision', async () => {
    const wrapper = await mount([approval(1)])
    wrapper.vm.confirmReject({ approval: approval(1), reason: 'Wait a week' })
    expect(wrapper.emitted('decide')[0][0]).toEqual({
      decisions: [{ id: 1, approved: false, reason: 'Wait a week' }],
      dontAskAgain: false,
    })
  })
})
