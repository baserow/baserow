import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test } from 'vitest'

import ShareScopeInput from '@baserow_enterprise/components/invitation/ShareScopeInput'

const roles = [
  { uid: 'EDITOR', name: 'Editor', isVisible: true, isDeactivated: false },
  { uid: 'VIEWER', name: 'Viewer', isVisible: true, isDeactivated: false },
]
const workspace = { id: 12, name: 'Widelab', _: { roles } }
const users = [{ user_id: 8, name: 'Mark Delgado', email: 'mark@x.com' }]
const teams = [{ id: 3, name: 'Management', subject_count: 2 }]
const agents = [{ id: 4, name: 'Smith' }]

async function mountInput(props = {}) {
  return await mountSuspended(ShareScopeInput, {
    props: {
      workspace,
      scopeTypeName: 'table',
      subjects: {
        'auth.User': users,
        'baserow_enterprise.Team': teams,
      },
      pendingEmails: ['olga@x.com'],
      roles,
      ...props,
    },
    global: {
      mocks: {
        // Shows the subject types the placeholder and empty text list.
        $t: (key, params) =>
          params?.subjects === undefined ? key : `${key}: ${params.subjects}`,
      },
      stubs: {
        WorkspaceRoleSelector: { template: '<div class="role"></div>' },
      },
    },
  })
}

function itemTitles(wrapper) {
  return wrapper.findAll('.invite-input__item-title').map((item) => item.text())
}

function tabLabels(wrapper) {
  return wrapper.findAll('.invite-input__tab').map((tab) => tab.text())
}

test('searches members and teams and offers an email for new people', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    await input.trigger('focus')
    expect(itemTitles(wrapper)).toEqual(['Mark Delgado', 'Management'])

    await input.setValue('mar')
    expect(itemTitles(wrapper)).toEqual(['Mark Delgado'])

    // A known member's address is not offered as a new invitation.
    await input.setValue('mark@x.com')
    expect(itemTitles(wrapper)).toEqual(['Mark Delgado'])

    await input.setValue('new@x.com')
    expect(itemTitles(wrapper)).toEqual(['inviteInput.inviteEmail'])
    expect(wrapper.find('.invite-input__item-subtitle').text()).toBe(
      'shareScope.inviteEmailDescription'
    )
  } finally {
    wrapper.unmount()
  }
})

test('lists an invited address and an assigned subject with the reason', async () => {
  const wrapper = await mountInput({
    assignedKeys: ['baserow_enterprise.Team:3'],
  })
  try {
    const input = wrapper.find('input')
    await input.trigger('focus')
    await input.setValue('Olga@x.com')

    const row = wrapper.find('.invite-input__item')
    expect(row.classes()).toContain('invite-input__item--disabled')
    expect(itemTitles(wrapper)).toEqual(['olga@x.com'])
    expect(wrapper.find('.invite-input__item-subtitle').text()).toBe(
      'shareScope.alreadyInvited'
    )
    expect(row.find('input').exists()).toBe(false)
    expect(wrapper.find('.invite-input__empty').exists()).toBe(false)

    // The row can't pick it, and the enter key only makes an error chip that
    // can't be submitted.
    await row.trigger('click')
    expect(wrapper.findAll('.invite-input__chip')).toHaveLength(0)
    await input.trigger('keydown', { key: 'Enter' })
    expect(
      wrapper.findAll('.invite-input__chip--error').map((chip) => chip.text())
    ).toEqual(['olga@x.com'])
    expect(
      wrapper.find('.invite-input__row button').attributes('disabled')
    ).toBeDefined()

    // A team that already holds a role on the object is listed the same way,
    // and so would a member or an agent be.
    await input.setValue('manage')
    expect(itemTitles(wrapper)).toEqual(['Management'])
    expect(wrapper.find('.invite-input__item').classes()).toContain(
      'invite-input__item--disabled'
    )
    expect(wrapper.find('.invite-input__item-subtitle').text()).toBe(
      'shareScope.alreadyAssigned'
    )
  } finally {
    wrapper.unmount()
  }
})

test('only mentions and offers the subject types it is given', async () => {
  const withoutAgents = await mountInput()
  try {
    const input = withoutAgents.find('input')
    expect(input.attributes('placeholder')).toBe(
      'shareScope.searchPlaceholder: subjecttype.members, subjecttype.teams'
    )
    await input.trigger('focus')
    expect(tabLabels(withoutAgents)).toEqual([
      'inviteInput.tabAll',
      'subjectType.members',
      'subjectType.teams',
    ])
    expect(itemTitles(withoutAgents)).toEqual(['Mark Delgado', 'Management'])

    await input.setValue('smith')
    expect(itemTitles(withoutAgents)).toEqual([])
    expect(withoutAgents.find('.invite-input__empty').text()).toBe(
      'shareScope.noResults: subjecttype.members or subjecttype.teams'
    )
  } finally {
    withoutAgents.unmount()
  }

  const withAgents = await mountInput({
    subjects: {
      'auth.User': users,
      'baserow_enterprise.Team': teams,
      'core.Agent': agents,
    },
  })
  try {
    const input = withAgents.find('input')
    expect(input.attributes('placeholder')).toBe(
      'shareScope.searchPlaceholder: subjecttype.members, subjecttype.teams, subjecttype.agents'
    )
    await input.trigger('focus')
    expect(tabLabels(withAgents)).toEqual([
      'inviteInput.tabAll',
      'subjectType.members',
      'subjectType.teams',
      'subjectType.agents',
    ])
    expect(itemTitles(withAgents)).toEqual([
      'Mark Delgado',
      'Management',
      'Smith',
    ])

    await input.setValue('nobody')
    expect(withAgents.find('.invite-input__empty').text()).toBe(
      'shareScope.noResults: subjecttype.members, subjecttype.teams, or subjecttype.agents'
    )
  } finally {
    withAgents.unmount()
  }
})

test('opens the tabs on focus even when there is nobody left to pick', async () => {
  const wrapper = await mountInput({
    subjects: { 'auth.User': [], 'baserow_enterprise.Team': [] },
  })
  try {
    await wrapper.find('input').trigger('focus')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'Context' }).vm.isOpen()).toBe(true)
    expect(tabLabels(wrapper)).toEqual([
      'inviteInput.tabAll',
      'subjectType.members',
      'subjectType.teams',
    ])
    expect(wrapper.find('.invite-input__empty').text()).toBe(
      'shareScope.noResults: subjecttype.members or subjecttype.teams'
    )
  } finally {
    wrapper.unmount()
  }
})

test('collects picks as chips and emits them with the role', async () => {
  const wrapper = await mountInput()
  try {
    const button = wrapper.find('.invite-input__row button')
    expect(button.attributes('disabled')).toBeDefined()

    const input = wrapper.find('input')
    await input.trigger('focus')
    await wrapper.find('.invite-input__item').trigger('click')
    await input.setValue('new@x.com')
    await input.trigger('keydown', { key: 'Enter' })

    const chips = wrapper.findAll('.invite-input__chip')
    expect(chips.map((chip) => chip.text())).toEqual([
      'Mark Delgado',
      'new@x.com',
    ])
    expect(input.element.value).toBe('')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(button.text()).toContain('shareScope.addAs')

    await button.trigger('click')
    const [picked, roleUid] = wrapper.emitted('add')[0]
    expect(picked.map((item) => item.key)).toEqual([
      'auth.User:8',
      'email:new@x.com',
    ])
    // The last role is the one with the least access, the safest default.
    expect(roleUid).toBe('VIEWER')

    wrapper.vm.reset()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.invite-input__chip')).toHaveLength(0)

    // The cross on a chip removes it again.
    await wrapper.find('.invite-input__item').trigger('click')
    await wrapper.find('.invite-input__chip-remove').trigger('click')
    expect(wrapper.findAll('.invite-input__chip')).toHaveLength(0)

    // The checkbox toggles through its own change event, not through the row.
    // The stubbed teleport of the results context renders its content anew,
    // so the checkbox is looked up again after every change.
    const checkbox = () => wrapper.find('.invite-input__item input')
    await checkbox().setValue(true)
    expect(wrapper.findAll('.invite-input__chip')).toHaveLength(1)
    await checkbox().setValue(false)
    expect(wrapper.findAll('.invite-input__chip')).toHaveLength(0)
  } finally {
    wrapper.unmount()
  }
})
