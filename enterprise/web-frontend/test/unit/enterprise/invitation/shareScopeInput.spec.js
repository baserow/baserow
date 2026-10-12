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
    .findAll('.share-scope-input__item-title')
    .map((item) => item.text())
}

function tabLabels(wrapper) {
  return wrapper.findAll('.share-scope-input__tab').map((tab) => tab.text())
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
    expect(itemTitles(wrapper)).toEqual(['shareScope.inviteEmail'])
    expect(wrapper.find('.share-scope-input__item-subtitle').text()).toBe(
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

    const row = wrapper.find('.share-scope-input__item')
    expect(row.classes()).toContain('share-scope-input__item--pending')
    expect(itemTitles(wrapper)).toEqual(['olga@x.com'])
    expect(wrapper.find('.share-scope-input__item-subtitle').text()).toBe(
      'shareScope.alreadyInvited'
    )
    expect(row.find('input').exists()).toBe(false)
    expect(wrapper.find('.share-scope-input__empty').exists()).toBe(false)

    // Neither the row nor the enter key can pick it.
    await row.trigger('click')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.findAll('.share-scope-input__chip')).toHaveLength(0)
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
      'shareScope.tabAll',
      'shareScope.tabMembers',
      'shareScope.tabTeams',
    ])
    expect(itemTitles(withoutAgents)).toEqual(['Mark Delgado', 'Management'])

    await input.setValue('smith')
    expect(itemTitles(withoutAgents)).toEqual([])
    expect(withoutAgents.find('.share-scope-input__empty').text()).toBe(
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
      'shareScope.tabAll',
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
    expect(withAgents.find('.share-scope-input__empty').text()).toBe(
      'shareScope.noResults'
    )
  } finally {
    withAgents.unmount()
  }
})

test('collects picks as chips and emits them with the role', async () => {
  const wrapper = await mountInput()
  try {
    const button = wrapper.find('.share-scope-input__row button')
    expect(button.attributes('disabled')).toBeDefined()

    const input = wrapper.find('input')
    await input.trigger('focus')
    await wrapper.find('.share-scope-input__item').trigger('click')
    await input.setValue('new@x.com')
    await input.trigger('keydown', { key: 'Enter' })

    const chips = wrapper.findAll('.share-scope-input__chip')
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
    expect(wrapper.findAll('.share-scope-input__chip')).toHaveLength(0)

    // The cross on a chip removes it again.
    await wrapper.find('.share-scope-input__item').trigger('click')
    await wrapper.find('.share-scope-input__chip-remove').trigger('click')
    expect(wrapper.findAll('.share-scope-input__chip')).toHaveLength(0)

    // The checkbox toggles through its own change event, not through the row.
    const checkbox = wrapper.find('.share-scope-input__item input')
    await checkbox.setValue(true)
    expect(wrapper.findAll('.share-scope-input__chip')).toHaveLength(1)
    await checkbox.setValue(false)
    expect(wrapper.findAll('.share-scope-input__chip')).toHaveLength(0)
  } finally {
    wrapper.unmount()
  }
})
