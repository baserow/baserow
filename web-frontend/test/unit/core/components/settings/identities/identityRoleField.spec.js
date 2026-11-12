import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test, vi } from 'vitest'

import IdentityRoleField from '@baserow/modules/core/components/settings/identities/IdentityRoleField'

const workspace = { id: 12 }
const identity = { id: 34, name: 'Row writer', role_uid: 'MEMBER' }
const roles = [
  { uid: 'MEMBER', name: 'Member', icon: 'baserow-icon-team' },
  { uid: 'ADMIN', name: 'Admin', icon: 'iconoir-crown' },
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
  dispatch = vi.fn().mockResolvedValue({ ...identity, role_uid: 'ADMIN' })
) =>
  mountSuspended(IdentityRoleField, {
    props: { row: identity, column },
    global: {
      mocks: {
        $store: { dispatch },
        $hasPermission: () => canUpdate,
      },
      stubs: { EditRoleContext: EditRoleContextStub },
    },
  })

describe('IdentityRoleField', () => {
  test('shows the current role as editable when identity updates are permitted', async () => {
    const wrapper = await mountField()

    await wrapper.find('.member-role-field__link').trigger('click')

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('shows the current role as read-only without identity update permission', async () => {
    const wrapper = await mountField(false)

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('updates the identity role directly from the table', async () => {
    const dispatch = vi.fn().mockResolvedValue({})
    const wrapper = await mountField(true, dispatch)

    await wrapper.find('.member-role-field__link').trigger('click')
    await wrapper.find('.change-role').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('row-update')).toEqual([
      [{ ...identity, role_uid: 'ADMIN' }],
    ])
    expect(dispatch).toHaveBeenCalledWith('identity/update', {
      identityId: 34,
      values: { role_uid: 'ADMIN' },
    })
  })
})
