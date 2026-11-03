import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test } from 'vitest'

import ScopeAccessList from '@baserow/modules/core/components/invitation/ScopeAccessList'

const roles = [{ uid: 'EDITOR', name: 'Editor' }]
const workspace = { id: 12, _: { roles } }

function item(key, extra = {}) {
  return {
    key,
    name: key,
    initials: 'A',
    color: 'blue',
    roleUid: 'EDITOR',
    ...extra,
  }
}

async function mountList(items) {
  return await mountSuspended(ScopeAccessList, {
    props: {
      items,
      roles,
      workspace,
      emptyTitle: 'Empty',
      emptyDescription: 'Nobody yet',
    },
    global: {
      stubs: {
        ScopeRoleSelector: { template: '<div class="role-selector"></div>' },
      },
    },
  })
}

test('only offers removal for a remove only row', async () => {
  const removable = item('team-member', { roleUid: null, removeOnly: true })
  const wrapper = await mountList([
    item('with-role'),
    item('locked-role', { roles: [] }),
    removable,
  ])

  expect(wrapper.findAll('.role-selector')).toHaveLength(2)
  const removeButtons = wrapper.findAll('.button-icon')
  expect(removeButtons).toHaveLength(1)

  await removeButtons[0].trigger('click')

  expect(wrapper.emitted('role-updated')).toEqual([[removable, null]])
})

test('disables the removal of a disabled row', async () => {
  const wrapper = await mountList([
    item('team-member', { roleUid: null, removeOnly: true, disabled: true }),
  ])

  expect(wrapper.find('.button-icon').attributes('disabled')).toBeDefined()
})
