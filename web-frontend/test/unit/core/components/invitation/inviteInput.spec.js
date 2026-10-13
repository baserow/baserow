import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test } from 'vitest'

import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'

const roles = [
  { uid: 'EDITOR', name: 'Editor', isVisible: true, isDeactivated: false },
  { uid: 'VIEWER', name: 'Viewer', isVisible: true, isDeactivated: false },
]
const workspace = { id: 12, name: 'Widelab', _: { roles } }

async function mountInput(props = {}) {
  return await mountSuspended(InviteInput, {
    props: {
      workspace,
      roles,
      pendingEmails: ['olga@x.com'],
      memberEmails: ['mark@x.com'],
      ...props,
    },
    global: {
      stubs: {
        WorkspaceRoleSelector: { template: '<div class="role"></div>' },
      },
    },
  })
}

function chips(wrapper) {
  return wrapper.findAll('.invite-input__chip').map((chip) => chip.text())
}

function errorChips(wrapper) {
  return wrapper
    .findAll('.invite-input__chip--error')
    .map((chip) => chip.text())
}

function itemTitles(wrapper) {
  return wrapper.findAll('.invite-input__item-title').map((item) => item.text())
}

function paste(input, text) {
  return input.trigger('paste', { clipboardData: { getData: () => text } })
}

test('only takes email addresses when there is nothing to search', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    const button = wrapper.find('.invite-input__row button')
    expect(input.attributes('placeholder')).toBe('inviteInput.placeholder')
    expect(button.text()).toBe('inviteInput.invite')
    expect(button.attributes('disabled')).toBeDefined()

    // Nothing to show until an address is typed: no tabs, no empty list.
    await input.trigger('focus')
    const results = wrapper.find('.invite-input__results')
    expect(results.attributes('style')).toContain('display: none')
    expect(wrapper.find('.invite-input__tabs').exists()).toBe(false)

    await input.setValue('new@x.com')
    expect(results.attributes('style') ?? '').not.toContain('display: none')
    expect(itemTitles(wrapper)).toEqual(['inviteInput.inviteEmail'])
    expect(wrapper.find('.invite-input__item-subtitle').text()).toBe(
      'inviteInput.inviteEmailDescription'
    )

    await input.trigger('keydown', { key: 'Enter' })
    expect(chips(wrapper)).toEqual(['new@x.com'])
    expect(button.text()).toContain('inviteInput.inviteAs')

    await button.trigger('click')
    const [picked, roleUid] = wrapper.emitted('add')[0]
    expect(picked.map(({ email }) => email)).toEqual(['new@x.com'])
    expect(roleUid).toBe('VIEWER')
  } finally {
    wrapper.unmount()
  }
})

test('turns a pasted list into chips and marks the ones it cannot invite', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    await input.trigger('focus')
    await paste(
      input,
      'Ann <ann@x.com>, BOB@x.com; olga@x.com\nmark@x.com not-an-address ann@x.com'
    )

    // Every address once, lower cased, names and junk dropped.
    expect(chips(wrapper)).toEqual([
      'ann@x.com',
      'bob@x.com',
      'olga@x.com',
      'mark@x.com',
    ])
    expect(input.element.value).toBe('')
    // The pending and the member address are chips too, marked as errors and
    // left out of what is submitted.
    expect(errorChips(wrapper)).toEqual(['olga@x.com', 'mark@x.com'])
    // The invitable addresses keep a checked row in the list, like a picked
    // member does, and can be unchecked from there.
    expect(itemTitles(wrapper)).toEqual([
      'inviteInput.inviteEmail',
      'inviteInput.inviteEmail',
    ])
    const rows = wrapper.findAll('.invite-input__item')
    expect(rows.map((row) => row.find('input').element.checked)).toEqual([
      true,
      true,
    ])
    await rows[0].trigger('click')
    expect(chips(wrapper)).toEqual(['bob@x.com', 'olga@x.com', 'mark@x.com'])
    expect(itemTitles(wrapper)).toEqual(['inviteInput.inviteEmail'])

    const button = wrapper.find('.invite-input__row button')
    expect(button.text()).toContain('inviteInput.inviteAs')
    await button.trigger('click')
    const [picked] = wrapper.emitted('add')[0]
    expect(picked.map(({ email }) => email)).toEqual(['bob@x.com'])
  } finally {
    wrapper.unmount()
  }
})

test('cannot submit when every chip is an error', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    await input.trigger('focus')
    await paste(input, 'olga@x.com')
    expect(errorChips(wrapper)).toEqual(['olga@x.com'])
    const button = wrapper.find('.invite-input__row button')
    expect(button.text()).toBe('inviteInput.invite')
    expect(button.attributes('disabled')).toBeDefined()
  } finally {
    wrapper.unmount()
  }
})

test('flags addresses while a role that cannot be used for invitations is chosen', async () => {
  const noAccess = {
    uid: 'NO_ACCESS',
    name: 'No access',
    isVisible: true,
    isDeactivated: false,
  }
  const member = {
    key: 'auth.User:8',
    type: 'auth.User',
    id: 8,
    name: 'Mark',
    search: 'mark',
    icon: 'iconoir-user',
    color: 'blue',
  }
  const wrapper = await mountInput({
    roles: [...roles, noAccess],
    emailRoleUids: ['EDITOR', 'VIEWER'],
    options: [member],
  })
  try {
    // No access is offered, but the default stays the last role an address
    // can be invited with.
    expect(wrapper.vm.roleUid).toBe('VIEWER')

    const input = wrapper.find('input')
    await input.trigger('focus')
    await input.setValue('new@x.com')
    await input.trigger('keydown', { key: 'Enter' })
    expect(errorChips(wrapper)).toEqual([])

    wrapper.vm.roleUid = 'NO_ACCESS'
    await wrapper.vm.$nextTick()
    expect(errorChips(wrapper)).toEqual(['new@x.com'])
    const button = wrapper.find('.invite-input__row button')
    expect(button.attributes('disabled')).toBeDefined()

    // A member can still be given no access.
    await input.setValue('mark')
    await wrapper.find('.invite-input__item').trigger('click')
    expect(button.attributes('disabled')).toBeUndefined()
    await button.trigger('click')
    const [picked, roleUid] = wrapper.emitted('add')[0]
    expect(picked.map(({ key }) => key)).toEqual(['auth.User:8'])
    expect(roleUid).toBe('NO_ACCESS')

    // Back to a role that works for everyone, the address is fine again.
    wrapper.vm.roleUid = 'VIEWER'
    await wrapper.vm.$nextTick()
    expect(errorChips(wrapper)).toEqual([])
  } finally {
    wrapper.unmount()
  }
})

test('clears a typed address once its member is picked from the list', async () => {
  const member = {
    key: 'auth.User:8',
    type: 'auth.User',
    id: 8,
    name: 'Foo Bar Viewer',
    email: 'foo@bar.com',
    search: 'Foo Bar Viewer foo@bar.com',
    icon: 'iconoir-user',
    color: 'blue',
  }
  const wrapper = await mountInput({ options: [member], memberEmails: [] })
  try {
    const input = wrapper.find('input')
    await input.trigger('focus')
    await input.setValue('foo@bar.com')
    // The member is offered, not a new invitation.
    expect(itemTitles(wrapper)).toEqual(['Foo Bar Viewer'])

    await wrapper.find('.invite-input__item').trigger('click')
    expect(chips(wrapper)).toEqual(['Foo Bar Viewer'])
    expect(input.element.value).toBe('')

    // Removing a chip must not take the focus, and with it the list, away
    // from the input.
    const mousedown = new MouseEvent('mousedown', {
      bubbles: true,
      cancelable: true,
    })
    expect(
      wrapper
        .find('.invite-input__chip-remove')
        .element.dispatchEvent(mousedown)
    ).toBe(false)

    // Searching by name keeps the search for the next pick.
    await wrapper.find('.invite-input__chip-remove').trigger('click')
    await input.setValue('foo bar')
    await wrapper.find('.invite-input__item').trigger('click')
    expect(chips(wrapper)).toEqual(['Foo Bar Viewer'])
    expect(input.element.value).toBe('foo bar')
  } finally {
    wrapper.unmount()
  }
})

test('leaves text without an address to the browser', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    await paste(input, 'just some words')
    expect(chips(wrapper)).toEqual([])
    expect(input.element.value).toBe('')
  } finally {
    wrapper.unmount()
  }
})

test('picks every typed address on enter', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    await input.trigger('focus')
    await input.setValue('one@x.com two@x.com, olga@x.com')
    expect(itemTitles(wrapper)).toEqual([
      'olga@x.com',
      'inviteInput.inviteEmail',
      'inviteInput.inviteEmail',
    ])

    await input.trigger('keydown', { key: 'Enter' })
    expect(chips(wrapper)).toEqual(['one@x.com', 'two@x.com', 'olga@x.com'])
    expect(errorChips(wrapper)).toEqual(['olga@x.com'])
    expect(input.element.value).toBe('')

    // Picking the same address again does nothing.
    await input.setValue('one@x.com')
    await input.trigger('keydown', { key: 'Enter' })
    expect(chips(wrapper)).toEqual(['one@x.com', 'two@x.com', 'olga@x.com'])
  } finally {
    wrapper.unmount()
  }
})
