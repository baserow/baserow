import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test } from 'vitest'

import ShareScopeInput from '@baserow_enterprise/components/invitation/ShareScopeInput'

const roles = [
  { uid: 'EDITOR', name: 'Editor', isVisible: true, isDeactivated: false },
  { uid: 'VIEWER', name: 'Viewer', isVisible: true, isDeactivated: false },
]
const workspace = { id: 12, name: 'Widelab', _: { roles } }

async function mountInput(props = {}) {
  return await mountSuspended(ShareScopeInput, {
    props: {
      workspace,
      scopeTypeName: 'table',
      users: [{ user_id: 8, name: 'Mark Delgado', email: 'mark@x.com' }],
      teams: [{ id: 3, name: 'Management', subject_count: 2 }],
      agents: [{ id: 4, name: 'Smith' }],
      pendingEmails: ['olga@x.com'],
      roles,
      ...props,
    },
    global: {
      stubs: {
        WorkspaceRoleSelector: { template: '<div class="role"></div>' },
      },
    },
  })
}

function itemTitles(wrapper) {
  return wrapper
    .findAll('.invite-input__item-title')
    .map((item) => item.text())
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

test('shows an already invited email as pending instead of offering it', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    await input.trigger('focus')
    await input.setValue('Olga@x.com')

    const row = wrapper.find('.invite-input__item')
    expect(row.classes()).toContain('invite-input__item--pending')
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
  } finally {
    wrapper.unmount()
  }
})

test('only mentions and offers agents while they are enabled', async () => {
  const withoutAgents = await mountInput()
  try {
    const input = withoutAgents.find('input')
    expect(input.attributes('placeholder')).toBe(
      'shareScope.searchPlaceholderWithoutAgents'
    )
    await input.trigger('focus')
    expect(tabLabels(withoutAgents)).toEqual([
      'inviteInput.tabAll',
      'shareScope.tabMembers',
      'shareScope.tabTeams',
    ])
    expect(itemTitles(withoutAgents)).toEqual(['Mark Delgado', 'Management'])

    await input.setValue('smith')
    expect(itemTitles(withoutAgents)).toEqual([])
    expect(withoutAgents.find('.invite-input__empty').text()).toBe(
      'shareScope.noResultsWithoutAgents'
    )
  } finally {
    withoutAgents.unmount()
  }

  const withAgents = await mountInput({ agentsEnabled: true })
  try {
    const input = withAgents.find('input')
    expect(input.attributes('placeholder')).toBe('shareScope.searchPlaceholder')
    await input.trigger('focus')
    expect(tabLabels(withAgents)).toEqual([
      'inviteInput.tabAll',
      'shareScope.tabMembers',
      'shareScope.tabTeams',
      'shareScope.tabAgents',
    ])
    expect(itemTitles(withAgents)).toEqual([
      'Mark Delgado',
      'Management',
      'Smith',
    ])

    await input.setValue('nobody')
    expect(withAgents.find('.invite-input__empty').text()).toBe(
      'shareScope.noResults'
    )
  } finally {
    withAgents.unmount()
  }
})

test('opens the tabs on focus even when there is nobody left to pick', async () => {
  const wrapper = await mountInput({ users: [], teams: [], agents: [] })
  try {
    await wrapper.find('input').trigger('focus')
    expect(wrapper.find('.invite-input__results').attributes('style') ?? '')
      .not.toContain('display: none')
    expect(tabLabels(wrapper)).toEqual([
      'inviteInput.tabAll',
      'shareScope.tabMembers',
      'shareScope.tabTeams',
    ])
    expect(wrapper.find('.invite-input__empty').text()).toBe(
      'shareScope.noResultsWithoutAgents'
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
    const checkbox = wrapper.find('.invite-input__item input')
    await checkbox.setValue(true)
    expect(wrapper.findAll('.invite-input__chip')).toHaveLength(1)
    await checkbox.setValue(false)
    expect(wrapper.findAll('.invite-input__chip')).toHaveLength(0)
  } finally {
    wrapper.unmount()
  }
})
