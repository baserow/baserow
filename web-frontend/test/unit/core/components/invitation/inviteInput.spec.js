import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test } from 'vitest'

import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'

const roles = [
  { uid: 'EDITOR', name: 'Editor', isVisible: true, isDeactivated: false },
  { uid: 'VIEWER', name: 'Viewer', isVisible: true, isDeactivated: false },
]
const workspace = { id: 12, name: 'Widelab', _: { roles } }
// Someone who can't be picked, with the reason the parent gives.
const member = {
  key: 'auth.User:8',
  type: 'auth.User',
  id: 8,
  name: 'Mark Delgado',
  email: 'mark@x.com',
  search: 'mark@x.com',
  initials: 'MD',
  icon: 'iconoir-user',
  color: 'blue',
  disabledReason: 'Already a member',
}
// An address with an invitation, listed the same way.
const pending = {
  key: 'invitation:olga@x.com',
  type: 'email',
  email: 'olga@x.com',
  name: 'olga@x.com',
  search: 'olga@x.com',
  icon: 'iconoir-mail',
  color: 'neutral',
  disabledReason: 'Already invited',
}
// Someone who can be picked.
const pickable = {
  key: 'auth.User:9',
  type: 'auth.User',
  id: 9,
  name: 'Foo Bar Viewer',
  email: 'foo@bar.com',
  search: 'Foo Bar Viewer foo@bar.com',
  initials: 'FV',
  icon: 'iconoir-user',
  color: 'blue',
}

async function mountInput(props = {}) {
  return await mountSuspended(InviteInput, {
    props: {
      workspace,
      roles,
      options: [member, pending],
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

function resultsOpen(wrapper) {
  return wrapper.findComponent({ name: 'Context' }).vm.isOpen()
}

function paste(input, text) {
  return input.trigger('paste', { clipboardData: { getData: () => text } })
}

test('only takes email addresses when there is nothing to pick', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    const button = wrapper.find('.invite-input__row button')
    expect(input.attributes('placeholder')).toBe('inviteInput.placeholder')
    expect(button.text()).toBe('inviteInput.invite')
    expect(button.attributes('disabled')).toBeDefined()

    // Nothing to show until an address is typed: no tabs, no list.
    await input.trigger('focus')
    expect(resultsOpen(wrapper)).toBe(false)
    expect(wrapper.find('.invite-input__tabs').exists()).toBe(false)

    await input.setValue('new@x.com')
    await flushPromises()
    expect(resultsOpen(wrapper)).toBe(true)
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

test('lists what cannot be picked with its reason and makes an error chip of it', async () => {
  const wrapper = await mountInput()
  try {
    const input = wrapper.find('input')
    await input.trigger('focus')
    await input.setValue('mark@x.com')

    const row = wrapper.find('.invite-input__item')
    expect(row.classes()).toContain('invite-input__item--disabled')
    expect(itemTitles(wrapper)).toEqual(['Mark Delgado'])
    expect(row.find('.invite-input__item-subtitle').text()).toBe(
      'Already a member'
    )
    expect(row.find('input').exists()).toBe(false)

    // The row can't be picked, and the enter key only makes an error chip.
    await row.trigger('click')
    expect(chips(wrapper)).toEqual([])
    await input.trigger('keydown', { key: 'Enter' })
    expect(errorChips(wrapper)).toEqual(['Mark Delgado'])
    expect(wrapper.vm.chipError(wrapper.vm.selected[0])).toBe(
      'Already a member'
    )
    expect(
      wrapper.find('.invite-input__row button').attributes('disabled')
    ).toBeDefined()

    // An address with an invitation is handled the same way.
    await input.setValue('Olga@x.com')
    expect(itemTitles(wrapper)).toEqual(['olga@x.com'])
    expect(wrapper.find('.invite-input__item-subtitle').text()).toBe(
      'Already invited'
    )
    await input.trigger('keydown', { key: 'Enter' })
    expect(errorChips(wrapper)).toEqual(['Mark Delgado', 'olga@x.com'])
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
      'Mark Delgado',
    ])
    expect(input.element.value).toBe('')
    // The invitation and the member are chips too, marked as errors and left
    // out of what is submitted.
    expect(errorChips(wrapper)).toEqual(['olga@x.com', 'Mark Delgado'])
    // Nothing can be picked from the list, so it only opens once searched.
    // The new addresses keep a checked row in it, like a picked member does,
    // and can be unchecked from there. What can't be picked shows up too, as
    // it is searched for.
    await input.setValue('@x')
    await flushPromises()
    expect(itemTitles(wrapper)).toEqual([
      'inviteInput.inviteEmail',
      'inviteInput.inviteEmail',
      'Mark Delgado',
      'olga@x.com',
    ])
    const rows = wrapper.findAll('.invite-input__item')
    expect(rows[0].find('input').element.checked).toBe(true)
    await rows[0].trigger('click')
    expect(chips(wrapper)).toEqual(['bob@x.com', 'olga@x.com', 'Mark Delgado'])

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
  const wrapper = await mountInput({
    roles: [...roles, noAccess],
    emailRoleUids: ['EDITOR', 'VIEWER'],
    options: [pickable],
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
    await input.setValue('foo bar')
    await wrapper.find('.invite-input__item').trigger('click')
    expect(button.attributes('disabled')).toBeUndefined()
    await button.trigger('click')
    const [picked, roleUid] = wrapper.emitted('add')[0]
    expect(picked.map(({ key }) => key)).toEqual(['auth.User:9'])
    expect(roleUid).toBe('NO_ACCESS')

    // Back to a role that works for everyone, the address is fine again.
    wrapper.vm.roleUid = 'VIEWER'
    await wrapper.vm.$nextTick()
    expect(errorChips(wrapper)).toEqual([])
  } finally {
    wrapper.unmount()
  }
})

test('clears a typed address once its option is picked from the list', async () => {
  const wrapper = await mountInput({ options: [pickable] })
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

    // Pasting the address of someone in the list picks them as well.
    await wrapper.find('.invite-input__chip-remove').trigger('click')
    await paste(input, 'foo@bar.com')
    expect(chips(wrapper)).toEqual(['Foo Bar Viewer'])
    expect(errorChips(wrapper)).toEqual([])
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
