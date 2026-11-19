import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test } from 'vitest'

import MembersRoleField from '@baserow_enterprise/components/MembersRoleField'
import enRaw from '@baserow_enterprise/locales/en.json?raw'

const roles = [
  { uid: 'ADMIN', name: 'Admin', isVisible: true },
  { uid: 'EDITOR', name: 'Editor', isVisible: true },
  { uid: 'NO_ROLE_LOW_PRIORITY', name: 'No role', isVisible: true },
]
const workspace = { id: 12, name: 'Widelab', _: { roles } }
const column = { key: 'role_uid', additionalProps: { workspaceId: 12 } }
const en = JSON.parse(enRaw)

// Translates with the English messages, picking the plural form by the count.
function translate(key, params = {}, count = 1) {
  const [namespace, name] = key.split('.')
  const forms = en[namespace][name].split(' | ')
  const message = forms[Math.min(count, forms.length) - 1]
  return message.replace(/{(\w+)}/g, (_, param) => params[param])
}

async function mountField(row) {
  return await mountSuspended(MembersRoleField, {
    props: { row: { id: 3, user_id: 8, ...row }, column },
    global: {
      mocks: {
        $hasPermission: () => true,
        $t: translate,
        $i18n: { locale: 'en' },
        $store: {
          getters: {
            'workspace/get': () => workspace,
            'auth/getUserId': 1,
          },
        },
      },
      stubs: {
        EditRoleContext: { template: '<div />', methods: { toggle() {} } },
        HelpIcon: {
          props: ['tooltip', 'icon'],
          template: '<i :class="icon">{{ tooltip }}</i>',
        },
      },
    },
  })
}

const teamRoleText = (wrapper) => {
  const teamRole = wrapper.find('.members-role-field__team-role')
  return teamRole.exists() ? teamRole.text() : null
}

test('shows the workspace role a member with no role takes from a team', async () => {
  const wrapper = await mountField({
    role_uid: 'NO_ROLE_LOW_PRIORITY',
    team_workspace_role: {
      role_uid: 'EDITOR',
      teams: [{ id: 1, name: 'Ops' }],
    },
  })

  // Shown as the tooltip of a team icon next to the role.
  expect(wrapper.find('.members-role-field__team-role').classes()).toContain(
    'iconoir-community'
  )
  expect(teamRoleText(wrapper)).toBe('Editor, through team Ops')
})

test('names every team giving the role', async () => {
  const wrapper = await mountField({
    role_uid: 'NO_ROLE_LOW_PRIORITY',
    team_workspace_role: {
      role_uid: 'EDITOR',
      teams: [
        { id: 2, name: 'Finance' },
        { id: 1, name: 'Ops' },
      ],
    },
  })

  expect(teamRoleText(wrapper)).toBe('Editor, through teams Finance and Ops')
})

test('says the role comes through teams the user may not see', async () => {
  const wrapper = await mountField({
    role_uid: 'NO_ROLE_LOW_PRIORITY',
    team_workspace_role: { role_uid: 'EDITOR', teams: [] },
  })

  expect(teamRoleText(wrapper)).toBe('Editor, through their teams')
})

test('shows nothing more without a role from a team', async () => {
  const wrapper = await mountField({
    role_uid: 'NO_ROLE_LOW_PRIORITY',
    team_workspace_role: null,
  })

  expect(teamRoleText(wrapper)).toBe(null)
})

test('shows nothing more once the member has a role of their own', async () => {
  // The row is changed before the members are fetched again.
  const wrapper = await mountField({
    role_uid: 'EDITOR',
    team_workspace_role: {
      role_uid: 'EDITOR',
      teams: [{ id: 1, name: 'Ops' }],
    },
  })

  expect(teamRoleText(wrapper)).toBe(null)
})
