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
    const button = wrapper.find('.invite-input__row button')
    expect(button.text()).toContain('inviteInput.inviteAs')
    await button.trigger('click')
    const [picked] = wrapper.emitted('add')[0]
    expect(picked.map(({ email }) => email)).toEqual(['ann@x.com', 'bob@x.com'])
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
