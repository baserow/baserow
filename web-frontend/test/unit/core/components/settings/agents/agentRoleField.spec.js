import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test, vi } from 'vitest'

import AgentRoleField from '@baserow/modules/core/components/settings/agents/AgentRoleField'

const workspace = { id: 12 }
const agent = { id: 34, name: 'Row writer', role_uid: 'MEMBER' }
const roles = [
  { uid: 'MEMBER', name: 'Member' },
  { uid: 'ADMIN', name: 'Admin' },
]
const column = { additionalProps: { roles, workspace } }

const EditRoleContextStub = {
  name: 'EditRoleContext',
  props: ['subject'],
  emits: ['update-role'],
  data: () => ({ visible: false }),
  methods: {
    toggle() {
      this.visible = !this.visible
    },
  },
  template: `
    <button
      v-if="visible"
      class="change-role"
      @click="$emit('update-role', { uid: 'ADMIN', subject })"
    />
  `,
}

const mountField = (
  canUpdate = true,
  dispatch = vi.fn().mockResolvedValue({ ...agent, role_uid: 'ADMIN' })
) =>
  mountSuspended(AgentRoleField, {
    props: { row: agent, column },
    global: {
      mocks: {
        $store: { dispatch },
        $hasPermission: () => canUpdate,
      },
      stubs: { EditRoleContext: EditRoleContextStub },
    },
  })

describe('AgentRoleField', () => {
  test('shows the current role as editable when agent updates are permitted', async () => {
    const wrapper = await mountField()

    await wrapper.find('.member-role-field__link').trigger('click')

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('shows the current role as read-only without agent update permission', async () => {
    const wrapper = await mountField(false)

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('updates the agent role directly from the table', async () => {
    const dispatch = vi.fn().mockResolvedValue({})
    const wrapper = await mountField(true, dispatch)

    await wrapper.find('.member-role-field__link').trigger('click')
    await wrapper.find('.change-role').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('row-update')).toEqual([
      [{ ...agent, role_uid: 'ADMIN' }],
    ])
    expect(dispatch).toHaveBeenCalledWith('agent/update', {
      agentId: 34,
      values: { role_uid: 'ADMIN' },
    })
  })
})
