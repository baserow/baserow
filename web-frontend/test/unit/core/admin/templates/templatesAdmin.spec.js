import { flushPromises } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { heldBack } from '@baserow/test/helpers/heldBack'
import { TemplatesAdminType } from '@baserow/modules/core/adminTypes'
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import TemplateNameField from '@baserow/modules/core/components/admin/templates/fields/TemplateNameField'
import TemplateAuthorField from '@baserow/modules/core/components/admin/templates/fields/TemplateAuthorField'
import TemplatesAdminTable from '@baserow/modules/core/components/admin/templates/TemplatesAdminTable'
import SidebarAdminItem from '@baserow/modules/core/components/sidebar/SidebarAdminItem'

vi.mock('lodash/debounce', () => ({
  default: vi.fn((fn) => Object.assign(fn, { cancel: () => {} })),
}))

const REVIEW_FIELDS = {
  'in_review:false': { can_reject: true, reject_unlists: false },
  'in_review:true': { can_reject: true, reject_unlists: false },
  'public:true': { can_reject: true, reject_unlists: true },
  'rejected:false': { can_reject: false, reject_unlists: false },
  'rejected:true': { can_reject: true, reject_unlists: true },
  'blocked:false': { can_reject: false, reject_unlists: false },
}

const row = (state, listed = false, canApprove = true) => ({
  id: 3,
  revision_id: 7,
  slug: 'sprint-a1b2c3',
  name: 'Sprint',
  state,
  listed,
  can_approve: canApprove,
  ...REVIEW_FIELDS[`${state}:${listed}`],
  workspace_id: 9,
  install_count: 14,
  submitted_on: null,
  author: { first_name: '', email: 'ada@example.com' },
  reviewed_on: '2026-11-02T10:00:00Z',
})

let testApp = null

beforeEach(() => {
  testApp = new TestApp()
})

afterEach(async () => {
  await testApp.afterEach()
})

describe('TemplatesAdminType', () => {
  test.each([true, false])(
    'is visible only with the user templates flag on (%s)',
    (enabled) => {
      const adminType = new TemplatesAdminType({
        app: {
          $featureFlagIsEnabled: (flag) =>
            flag === FF_USER_TEMPLATES && enabled,
        },
      })

      expect(adminType.isVisible()).toBe(enabled)
    }
  )
})

describe('TemplatesAdminTable', () => {
  const mountTable = async (
    rows,
    {
      count = rows.length,
      counts = { in_review: 1, public: 1, rejected: 0, blocked: 0 },
      component = TemplatesAdminTable,
    } = {}
  ) => {
    testApp.mock.onGet('/admin/templates/').reply(200, { count, results: rows })
    testApp.mock.onGet('/admin/templates/counts/').reply(200, counts)
    testApp.mock.onGet('/applications/workspace/9/').reply(200, [])
    const wrapper = await testApp.mount(component)
    await flushPromises()
    return wrapper
  }

  const PageWithSidebar = defineComponent({
    render: () => [
      h(SidebarAdminItem, {
        adminType: testApp.getRegistry().get('admin', 'templates'),
      }),
      h(TemplatesAdminTable),
    ],
  })

  const requestsTo = (url) =>
    testApp.mock.history.get.filter((request) => request.url === url)

  const bodyButton = (label) =>
    [...document.body.querySelectorAll('button')].find(
      (button) => button.textContent.trim() === label
    )

  const rowButton = (wrapper, label) =>
    wrapper.findAll('button').find((button) => button.text() === label)

  const previewButtons = () =>
    [
      ...document.body.querySelectorAll(
        '.templates-admin-review-actions button'
      ),
    ].map((button) => button.textContent.trim())

  const menuLinks = () => [
    ...document.body.querySelectorAll(
      '.context:not(.visibility-hidden) .context__menu-item-link'
    ),
  ]
  const label = (link) =>
    [...link.childNodes]
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent)
      .join('')
      .trim()
  const menuLabels = () => menuLinks().map(label)

  const openMenu = async (wrapper, index = 0) => {
    await wrapper.findAll('.data-table__more').at(index).trigger('click')
    await flushPromises()
  }

  const clickMenuItem = async (text) => {
    menuLinks()
      .find((link) => label(link) === text)
      .dispatchEvent(new MouseEvent('click', { bubbles: false }))
    await flushPromises()
  }

  const escape = async () => {
    window.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape' }))
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve))
  }

  const typeReason = async (reason) => {
    const input = document.body.querySelector('.user-template-modal input')
    input.value = reason
    input.dispatchEvent(new Event('input'))
    await flushPromises()
  }

  const submitReject = async (action, reason = 'Spam') => {
    await typeReason(reason)
    bodyButton(`rejectTemplateModal.${action}`).click()
    await flushPromises()
  }

  const expectRefreshed = async ({ lists = 2, scrolls = true } = {}) => {
    expect(requestsTo('/admin/templates/').length).toBe(lists)
    expect(requestsTo('/admin/templates/counts/').length).toBe(2)
    if (scrolls) {
      expect(document.body.classList.contains('prevent-scroll')).toBe(false)
    }
    await new Promise((resolve) => setTimeout(resolve))
    expect(previewButtons()).toEqual([])
  }

  test('lists the templates of the chosen tab with its counts', async () => {
    const wrapper = await mountTable(
      [{ id: 3, revision_id: 7, name: 'Sprint', author: null, reason: 'Spam' }],
      { counts: { in_review: 4, public: 12, rejected: 2, blocked: 1 } }
    )
    const listStates = () =>
      requestsTo('/admin/templates/').map((request) => request.params.state)
    const headers = () =>
      wrapper.findAll('.data-table__table-cell--header').map((h) => h.text())

    expect(wrapper.find('.data-table__subtitle').text()).toBe(
      'templatesAdmin.subtitle'
    )
    expect(listStates()).toEqual(['in_review'])
    expect(requestsTo('/admin/templates/counts/').length).toBe(1)
    expect(headers()).toContain('templatesAdmin.submitted')

    await wrapper.findAll('.tabs__item').at(2).trigger('click')
    await flushPromises()

    expect(listStates()).toEqual(['in_review', 'rejected'])
    expect(requestsTo('/admin/templates/counts/').length).toBe(2)
    expect(headers()).toContain('templatesAdmin.reason')
    expect(headers()).not.toContain('templatesAdmin.submitted')

    await wrapper.findAll('.tabs__item').at(3).trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.tabs__item').at(3).text()).toBe(
      'templatesAdmin.tabCount - 1'
    )
    expect(listStates()).toEqual(['in_review', 'rejected', 'blocked'])
    expect(requestsTo('/admin/templates/counts/').length).toBe(3)
    expect(headers()).toContain('templatesAdmin.reason')
  })

  test('tells when the tab has no templates', async () => {
    const wrapper = await mountTable([], {
      counts: { in_review: 0, public: 0, rejected: 0, blocked: 0 },
    })

    expect(wrapper.find('.data-table__empty').text()).toBe(
      'templatesAdmin.inReviewEmpty'
    )
  })

  const clickAction = async (wrapper, template, action) => {
    if (['block', 'unblock'].includes(action)) {
      await openMenu(wrapper)
      await clickMenuItem(`templatesAdmin.${action}`)
    } else if (template.state === 'public') {
      await openMenu(wrapper)
      await clickMenuItem('templatesAdmin.unlistFromBrowser')
    } else {
      await rowButton(wrapper, 'templatesAdmin.review').trigger('click')
      await flushPromises()
      bodyButton(`templatesAdmin.${action}`).click()
    }
    await flushPromises()
  }

  test.each([
    ['in_review', false, ['templatesAdmin.reject', 'templatesAdmin.approve']],
    ['rejected', false, ['templatesAdmin.approve']],
    ['rejected', true, ['templatesAdmin.unlist', 'templatesAdmin.approve']],
  ])(
    'reviews a %s template (listed: %s) in its preview',
    async (state, listed, labels) => {
      const wrapper = await mountTable([row(state, listed)])

      await rowButton(wrapper, 'templatesAdmin.review').trigger('click')
      await flushPromises()

      expect(previewButtons()).toEqual(labels)
      expect(
        document.body.querySelector('.template-details__author-name')
          .textContent
      ).toBe('ada@example.com')
    }
  )

  test('approves from the preview, then closes it and refreshes the list and counts', async () => {
    testApp.mock
      .onPost('/admin/templates/3/approve/')
      .reply(200, row('public', true))
    const wrapper = await mountTable([row('in_review')], { count: 150 })

    await wrapper.find('.paginator__button:last-child').trigger('click')
    await flushPromises()
    expect(testApp.mock.history.get.at(-1).params.page).toBe(2)
    expect(requestsTo('/admin/templates/counts/').length).toBe(1)

    await rowButton(wrapper, 'templatesAdmin.review').trigger('click')
    await flushPromises()
    bodyButton('templatesAdmin.approve').click()
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      revision_id: 7,
      state: 'in_review',
      listed: false,
      reviewed_on: '2026-11-02T10:00:00Z',
    })
    expect(testApp.store.state.toast.items).toEqual([])
    await expectRefreshed({ lists: 3 })
  })

  test.each([['ERROR_USER_NOT_IN_GROUP'], ['ERROR_GROUP_DOES_NOT_EXIST']])(
    'tells that the template changed when its preview fails with %s, then refreshes',
    async (error) => {
      const wrapper = await mountTable([row('in_review')])
      testApp.mock
        .onGet('/applications/workspace/9/')
        .reply(400, { error, detail: 'Changed.' })

      await rowButton(wrapper, 'templatesAdmin.review').trigger('click')
      await flushPromises()

      expect(testApp.store.state.toast.items).toMatchObject([
        { type: 'error', title: 'templatesAdmin.changedTitle' },
      ])
      await expectRefreshed({ scrolls: false })
    }
  )

  test.each([
    ['in_review', false, 'reject', 'title', 'description'],
    ['in_review', true, 'reject', 'title', 'editDescription'],
    ['public', true, 'unlist', 'unlistTitle', 'unlistDescription'],
    ['rejected', true, 'unlist', 'unlistTitle', 'unlistDescription'],
  ])(
    'rejects a %s template (listed: %s) with the trimmed reason, then refreshes',
    async (state, listed, action, title, description) => {
      const template = row(state, listed)
      testApp.mock
        .onPost('/admin/templates/3/reject/')
        .reply(200, { ...template, state: 'rejected', listed: false })
      const wrapper = await mountTable([template])

      await clickAction(wrapper, template, action)
      expect(document.body.classList.contains('prevent-scroll')).toBe(true)
      const modal = document.body.querySelector('.user-template-modal')
      expect(document.activeElement).toBe(modal.querySelector('input'))
      expect(modal.querySelector('h2').textContent).toBe(
        `rejectTemplateModal.${title}`
      )
      expect(modal.querySelector('p').textContent.trim()).toBe(
        `rejectTemplateModal.${description}`
      )
      for (const reason of ['', '   ']) {
        await typeReason(reason)
        expect(bodyButton(`rejectTemplateModal.${action}`).disabled).toBe(true)
      }
      await submitReject(action, '  Spam ')

      expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
        revision_id: 7,
        reason: 'Spam',
        state,
        listed,
        reviewed_on: '2026-11-02T10:00:00Z',
      })
      expect(testApp.store.state.toast.items).toEqual([])
      await expectRefreshed()
    }
  )

  test.each([
    ['public', 'block', { reason: 'Spam' }],
    ['blocked', 'unblock', undefined],
  ])(
    'moderates a %s template with %s from its menu, then refreshes',
    async (state, action, body) => {
      const template = row(state, state === 'public')
      testApp.mock
        .onPost(`/admin/templates/3/${action}/`)
        .reply(200, { ...template, state: 'blocked' })
      const wrapper = await mountTable([template])

      await clickAction(wrapper, template, action)
      if (body) {
        const modal = document.body.querySelector('.user-template-modal')
        expect(modal.querySelector('h2').textContent).toBe(
          'rejectTemplateModal.blockTitle'
        )
        expect(bodyButton('rejectTemplateModal.block').disabled).toBe(true)
        await submitReject('block', '  Spam ')
      }

      expect(testApp.mock.history.post.map(({ url }) => url)).toEqual([
        `/admin/templates/3/${action}/`,
      ])
      expect(
        body && JSON.parse(testApp.mock.history.post[0].data)
      ).toStrictEqual(body)
      expect(testApp.store.state.toast.items).toEqual([])
      await expectRefreshed()
    }
  )

  test('keeps the block copy while the modal closes, and each open sets its own', async () => {
    const blocked = row('public', true)
    const reviewed = { ...row('in_review'), id: 4, revision_id: 8 }
    const wrapper = await mountTable([blocked, reviewed])
    const title = () =>
      document.body.querySelector('.user-template-modal h2').textContent

    await clickAction(wrapper, blocked, 'block')
    bodyButton('action.cancel').click()
    await nextTick()

    expect(title()).toBe('rejectTemplateModal.blockTitle')
    expect(bodyButton('rejectTemplateModal.block')).toBeDefined()

    await new Promise((resolve) => setTimeout(resolve))
    await clickAction(wrapper, reviewed, 'reject')

    expect(title()).toBe('rejectTemplateModal.title')
    expect(bodyButton('rejectTemplateModal.reject')).toBeDefined()
  })

  test.each([['approve'], ['reject']])(
    "doesn't let the %s of a template affect the preview of another one",
    async (action) => {
      const { reply, send } = heldBack()
      testApp.mock.onPost(`/admin/templates/3/${action}/`).reply(reply)
      const other = {
        ...row('in_review'),
        id: 4,
        revision_id: 8,
        name: 'Other',
      }
      const wrapper = await mountTable([row('in_review'), other])

      await clickAction(wrapper, row('in_review'), action)
      if (action === 'reject') {
        await submitReject('reject')
        await escape()
      }
      await escape()
      const reviewButtons = wrapper
        .findAll('button')
        .filter((button) => button.text() === 'templatesAdmin.review')
      await reviewButtons[1].trigger('click')
      await flushPromises()
      expect(bodyButton('templatesAdmin.approve').disabled).toBe(false)

      send([200, row('public', true)])
      await flushPromises()
      await new Promise((resolve) => setTimeout(resolve))

      expect(requestsTo('/admin/templates/').length).toBe(2)
      expect(
        document.body.querySelector('.template-details__name').textContent
      ).toBe('Other')
      expect(bodyButton('templatesAdmin.approve').disabled).toBe(false)
    }
  )

  test.each([
    [true, 'templatesAdmin.editedSinceSubmitted'],
    [false, 'templatesAdmin.noContent'],
  ])(
    "tells why a template can't be approved (edited: %s)",
    async (edited, hint) => {
      const wrapper = await mountTable([
        { ...row('rejected', false, false), edited_since_submitted: edited },
      ])

      await rowButton(wrapper, 'templatesAdmin.review').trigger('click')
      await flushPromises()

      expect(bodyButton('templatesAdmin.approve').disabled).toBe(true)
      expect(
        document.body.querySelector('.templates-admin-review-hint').textContent
      ).toContain(hint)
    }
  )

  test('keeps the preview out of reach under its reject modal, until escape closes it', async () => {
    const template = row('in_review')
    const wrapper = await mountTable([template])
    await clickAction(wrapper, template, 'reject')

    expect(
      bodyButton('templatesAdmin.approve').closest('[inert]')
    ).not.toBeNull()

    await escape()

    expect(document.body.querySelector('.user-template-modal')).toBeNull()
    expect(previewButtons()).toEqual([
      'templatesAdmin.reject',
      'templatesAdmin.approve',
    ])
    expect(bodyButton('templatesAdmin.approve').closest('[inert]')).toBeNull()
    expect(document.activeElement).toBe(bodyButton('templatesAdmin.reject'))
  })

  test('focuses the preview once loaded, and gives the focus back on close', async () => {
    const wrapper = await mountTable([row('in_review')])
    const review = rowButton(wrapper, 'templatesAdmin.review').element
    review.focus()

    review.click()
    await flushPromises()
    expect(document.activeElement.classList).toContain(
      'template-details__back-link'
    )

    await escape()
    expect(document.activeElement).toBe(review)
  })

  test.each([
    ['its row', [row('in_review')], '.templates-admin-actions button'],
    ['the table once its row left the tab', [], '.data-table__table'],
  ])(
    'gives the focus to %s after the review',
    async (name, rowsAfter, focused) => {
      testApp.mock
        .onPost('/admin/templates/3/approve/')
        .reply(200, row('public', true))
      const wrapper = await mountTable([row('in_review')])
      const review = rowButton(wrapper, 'templatesAdmin.review').element
      review.focus()
      review.click()
      await flushPromises()
      testApp.mock
        .onGet('/admin/templates/')
        .reply(200, { count: rowsAfter.length, results: rowsAfter })

      bodyButton('templatesAdmin.approve').click()
      await flushPromises()
      await new Promise((resolve) => setTimeout(resolve))

      expect(document.activeElement).toBe(wrapper.find(focused).element)
    }
  )

  test.each([
    ['until the content is loaded', 200, false, 0],
    ['when the content fails to load', 500, true, 0],
    ['for the next template until its content is loaded', 200, false, 1],
  ])(
    'keeps the review actions disabled %s, and tells when it fails',
    async (name, status, stays, opened) => {
      const next = {
        ...row('in_review'),
        id: 4,
        revision_id: 8,
        workspace_id: 10,
      }
      const wrapper = await mountTable([row('in_review'), next])
      const { reply, send } = heldBack()
      testApp.mock
        .onGet(`/applications/workspace/${[9, 10][opened]}/`)
        .reply(reply)
      const disabled = () =>
        ['templatesAdmin.reject', 'templatesAdmin.approve'].map(
          (label) => bodyButton(label).disabled
        )
      const reviewButtons = wrapper
        .findAll('button')
        .filter((button) => button.text() === 'templatesAdmin.review')

      if (opened) {
        await reviewButtons[0].trigger('click')
        await flushPromises()
        expect(disabled()).toEqual([false, false])
        await escape()
      }
      await reviewButtons[opened].trigger('click')
      await flushPromises()
      expect(disabled()).toEqual([true, true])

      send([status, status === 200 ? [] : {}])
      await flushPromises()

      expect(disabled()).toEqual([stays, stays])
      expect(
        testApp.store.state.toast.items.map((toast) => toast.title)
      ).toEqual(stays ? ['clientHandler.notCompletedTitle'] : [])
    }
  )

  test("doesn't swap the template while its reject modal is open", async () => {
    const listed = { ...row('public', true), id: 4 }
    testApp.mock.onPost('/admin/templates/4/reject/').reply(200, listed)
    const wrapper = await mountTable([listed, row('in_review')])
    await clickAction(wrapper, listed, 'unlist')

    await rowButton(wrapper, 'templatesAdmin.review').trigger('click')
    await submitReject('unlist')

    expect(testApp.mock.history.post.map((request) => request.url)).toEqual([
      '/admin/templates/4/reject/',
    ])
    expect(previewButtons()).toEqual([])
  })

  test.each([
    ['approve', row('in_review'), 'ERROR_TEMPLATE_UPDATED', 'changedTitle'],
    [
      'reject',
      row('in_review'),
      'ERROR_TEMPLATE_ALREADY_REJECTED',
      'alreadyRejectedTitle',
    ],
    [
      'unlist',
      row('public', true),
      'ERROR_TEMPLATE_ALREADY_REJECTED',
      'alreadyUnlistedTitle',
    ],
    [
      'block',
      row('public', true),
      'ERROR_TEMPLATE_DOES_NOT_EXIST',
      'changedTitle',
    ],
  ])(
    'tells that the template changed when the %s fails, then refreshes',
    async (action, template, error, title) => {
      const endpoint = action === 'unlist' ? 'reject' : action
      testApp.mock
        .onPost(`/admin/templates/3/${endpoint}/`)
        .reply(400, { error, detail: 'Changed.' })
      const wrapper = await mountTable([template])

      await clickAction(wrapper, template, action)
      if (action !== 'approve') {
        await submitReject(action)
      }

      expect(testApp.store.state.toast.items).toMatchObject([
        { type: 'error', title: `templatesAdmin.${title}` },
      ])
      await expectRefreshed()
    }
  )

  test.each([
    [
      0,
      'in_review',
      'templatesAdmin.submitted',
      [
        'templatesAdmin.template',
        'templatesAdmin.author',
        'templatesAdmin.submitted',
      ],
      ['templatesAdmin.review'],
      [
        'templateInstall.download',
        'templatesAdmin.block',
        'templatesAdmin.delete',
      ],
      '',
    ],
    [
      1,
      'public',
      'templatesAdmin.used',
      [
        'templatesAdmin.template',
        'templatesAdmin.author',
        'templatesAdmin.used',
      ],
      [],
      [
        'templatesAdmin.viewInTemplates',
        'templateInstall.copyLink',
        'templateInstall.download',
        'templatesAdmin.unlistFromBrowser',
        'templatesAdmin.block',
        'templatesAdmin.delete',
      ],
      '14 times',
    ],
    [
      2,
      'rejected',
      'templatesAdmin.reason',
      ['templatesAdmin.template', 'templatesAdmin.author'],
      ['templatesAdmin.review'],
      [
        'templatesAdmin.approveAfterAll',
        'templateInstall.download',
        'templatesAdmin.block',
        'templatesAdmin.delete',
      ],
      '',
    ],
    [
      3,
      'blocked',
      'templatesAdmin.reason',
      ['templatesAdmin.template', 'templatesAdmin.author'],
      [],
      [
        'templatesAdmin.preview',
        'templateInstall.download',
        'templatesAdmin.unblock',
        'templatesAdmin.delete',
      ],
      '',
    ],
  ])(
    'shows the columns, row button and menu of the tab %s (%s)',
    async (tabIndex, state, column, sortable, buttons, items, cell) => {
      const wrapper = await mountTable([row(state, state === 'public')])
      await wrapper.findAll('.tabs__item').at(tabIndex).trigger('click')
      await flushPromises()

      expect(
        wrapper.findAll('.data-table__table-cell--header').map((h) => h.text())
      ).toEqual([
        'templatesAdmin.template',
        'templatesAdmin.author',
        column,
        '',
      ])
      expect(
        wrapper
          .findAll('.data-table__table-cell-head-link')
          .map((button) => button.text())
      ).toEqual(sortable)
      expect(wrapper.findAll('tbody td').at(2).text()).toBe(cell)
      expect(
        wrapper
          .findAll('tbody button:not(.data-table__more)')
          .map((button) => button.text())
      ).toEqual(buttons)

      await openMenu(wrapper)

      expect(menuLabels()).toEqual(items)
    }
  )

  test('offers Download of a blocked template to its author too', async () => {
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    const wrapper = await mountTable([
      {
        ...row('blocked'),
        author: { id: 1, first_name: '', email: 'ada@example.com' },
      },
    ])
    await wrapper.findAll('.tabs__item').at(3).trigger('click')
    await flushPromises()

    await openMenu(wrapper)
    expect(menuLabels()).toContain('templateInstall.download')
  })

  test('previews a blocked template and unblocks it there, then refreshes', async () => {
    testApp.authenticate({ id: 1, preferences: {}, is_staff: true })
    testApp.mock
      .onPost('/admin/templates/3/unblock/')
      .reply(200, row('private'))
    const wrapper = await mountTable([
      { ...row('blocked'), type: 'user', reason: 'Spam' },
    ])

    await openMenu(wrapper)
    await clickMenuItem('templatesAdmin.preview')
    expect(previewButtons()).toEqual([])
    expect(document.body.querySelector('.template-details__state')).not.toBe(
      null
    )
    document.body
      .querySelector('.template-install__actions .button-icon')
      .click()
    await flushPromises()
    await clickMenuItem('templatesAdmin.unblock')

    expect(testApp.mock.history.post.map(({ url }) => url)).toEqual([
      '/admin/templates/3/unblock/',
    ])
    await expectRefreshed()
  })

  test('copies the link everybody opens', async () => {
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn() } })
    try {
      const wrapper = await mountTable([row('public', true)])

      await openMenu(wrapper)
      await clickMenuItem('templateInstall.copyLink')

      const url = new URL(navigator.clipboard.writeText.mock.calls[0][0])
      expect(url.pathname).toBe('/template/sprint-a1b2c3')
      expect(url.search).toBe('')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  test('shows copied once the link is copied', async () => {
    vi.stubGlobal('navigator', {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
    try {
      const wrapper = await mountTable([row('public', true)])

      await openMenu(wrapper)
      await clickMenuItem('templateInstall.copyLink')
      await flushPromises()

      expect(document.body.querySelector('.copied--show')).not.toBe(null)
      expect(testApp.store.state.toast.items).toEqual([])
    } finally {
      vi.unstubAllGlobals()
    }
  })

  test('shows an error instead of copied when the link cannot be copied', async () => {
    vi.stubGlobal('navigator', {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    })
    try {
      const wrapper = await mountTable([row('public', true)])

      await openMenu(wrapper)
      await clickMenuItem('templateInstall.copyLink')

      expect(testApp.store.state.toast.items[0]).toMatchObject({
        type: 'error',
        title: 'copied.linkFailed',
      })
      expect(document.body.querySelector('.copied--show')).toBe(null)
    } finally {
      vi.unstubAllGlobals()
    }
  })

  test('shows a published template among the shared templates, searched by its name', async () => {
    testApp.mock
      .onGet('/templates/')
      .reply(({ params }) => [
        200,
        params?.listed ? { count: 0, next: null, results: [] } : [],
      ])
    testApp.authenticate({ id: 1 })
    const wrapper = await mountTable([row('public', true)])

    await openMenu(wrapper)
    await clickMenuItem('templatesAdmin.viewInTemplates')
    await flushPromises()

    const listed = requestsTo('/templates/').filter(
      ({ params }) => params?.listed
    )
    expect(listed.map(({ params }) => params.search)).toEqual(['Sprint'])
    expect(
      document.body.querySelector(
        '.public-template-list .template-list__search input'
      ).value
    ).toBe('Sprint')
    expect(previewButtons()).toEqual([])
  })

  test('approves a rejected template after all, then refreshes the list and counts', async () => {
    testApp.mock.onPost('/admin/templates/3/approve/').reply(200, {})
    const wrapper = await mountTable([row('rejected')])

    await openMenu(wrapper)
    await clickMenuItem('templatesAdmin.approveAfterAll')

    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      revision_id: 7,
      state: 'rejected',
      listed: false,
      reviewed_on: '2026-11-02T10:00:00Z',
    })
    expect(requestsTo('/admin/templates/').length).toBe(2)
    expect(requestsTo('/admin/templates/counts/').length).toBe(2)
    expect(menuLabels()).toEqual([])
  })

  test('deletes a template once confirmed, then refreshes the list, counts and badge', async () => {
    testApp.mock.onDelete('/templates/sprint-a1b2c3/').reply(204)
    const wrapper = await mountTable([row('in_review')], {
      component: PageWithSidebar,
    })
    expect(requestsTo('/admin/templates/counts/').length).toBe(1)
    expect(wrapper.find('.badge-counter--warning').text()).toBe('1')

    await openMenu(wrapper)
    await clickMenuItem('templatesAdmin.delete')
    expect(testApp.mock.history.delete).toHaveLength(0)
    testApp.mock
      .onGet('/admin/templates/')
      .reply(200, { count: 0, results: [] })
    testApp.mock
      .onGet('/admin/templates/counts/')
      .reply(200, { in_review: 0, public: 1, rejected: 0 })
    bodyButton('deleteUserTemplateModal.delete').click()
    await flushPromises()

    expect(testApp.mock.history.delete.map(({ url }) => url)).toEqual([
      '/templates/sprint-a1b2c3/',
    ])
    expect(wrapper.find('.templates-admin-name').exists()).toBe(false)
    expect(requestsTo('/admin/templates/').length).toBe(2)
    expect(requestsTo('/admin/templates/counts/').length).toBe(2)
    expect(wrapper.find('.badge-counter').exists()).toBe(false)
  })

  test('loads the badge on another admin page, once for its sidebar', async () => {
    testApp.mock
      .onGet('/admin/templates/counts/')
      .reply(200, { in_review: 3, public: 0, rejected: 0 })
    const props = { adminType: testApp.getRegistry().get('admin', 'templates') }

    const item = await testApp.mount(SidebarAdminItem, { props })
    await flushPromises()
    await testApp.mount(SidebarAdminItem, { props })
    await flushPromises()

    expect(item.find('.badge-counter--warning').text()).toBe('3')
    expect(requestsTo('/admin/templates/counts/').length).toBe(1)
  })

  test('refreshes the list and counts when the downloaded template changed since', async () => {
    testApp.mock.onPost('/templates/sprint-a1b2c3/download/').reply(400, {
      error: 'ERROR_TEMPLATE_UPDATED',
      detail: 'Changed.',
    })
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    const wrapper = await mountTable([row('in_review')])

    await openMenu(wrapper)
    await clickMenuItem('templateInstall.download')

    expect(testApp.mock.history.post).toHaveLength(1)
    expect(requestsTo('/admin/templates/').length).toBe(2)
    expect(requestsTo('/admin/templates/counts/').length).toBe(2)
  })

  test('keeps the menu of another row open when a download ends', async () => {
    let finish = null
    testApp.mock.onPost('/templates/sprint-a1b2c3/download/').reply(
      () =>
        new Promise((resolve) => {
          finish = () =>
            resolve([400, { error: 'ERROR_TEMPLATE_HAS_NO_CONTENT' }])
        })
    )
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    const other = { ...row('in_review'), id: 4, slug: 'other-d4e5f6' }
    const wrapper = await mountTable([row('in_review'), other])

    await openMenu(wrapper, 0)
    await clickMenuItem('templateInstall.download')
    await openMenu(wrapper, 1)
    finish()
    await flushPromises()

    expect(menuLabels()).toEqual([
      'templateInstall.download',
      'templatesAdmin.block',
      'templatesAdmin.delete',
    ])
  })

  test('keeps the counts of the newest request when an older one ends first', async () => {
    const counts = (inReview) => ({
      in_review: inReview,
      public: 0,
      rejected: 0,
    })
    const replies = []
    testApp.mock
      .onGet('/admin/templates/counts/')
      .reply(() => new Promise((resolve) => replies.push(resolve)))
    const { dispatch, getters } = testApp.store

    const older = dispatch('templatesAdmin/fetchCounts')
    const newest = dispatch('templatesAdmin/fetchCounts', { force: true })
    await flushPromises()
    replies[0]([200, counts(5)])
    await older

    expect(getters['templatesAdmin/counts']).toBe(null)

    replies[1]([200, counts(2)])
    await newest

    expect(getters['templatesAdmin/inReviewCount']).toBe(2)
  })

  test('leaves the badge hidden without a toast when the counts fail', async () => {
    testApp.mock.onGet('/admin/templates/counts/').reply(500)
    const { dispatch, getters } = testApp.store

    await expect(
      dispatch('templatesAdmin/ensureCounts')
    ).resolves.toBeUndefined()

    expect(getters['templatesAdmin/counts']).toBe(null)
    expect(testApp.store.state.toast.items).toEqual([])
  })

  test('forgets the counts when the user data is cleared', async () => {
    testApp.mock
      .onGet('/admin/templates/counts/')
      .reply(200, { in_review: 3, public: 0, rejected: 0 })
    const { dispatch, getters } = testApp.store
    await dispatch('templatesAdmin/fetchCounts')

    await dispatch('auth/clearAllStoreUserData')

    expect(getters['templatesAdmin/counts']).toBe(null)
  })

  test('drops the counts request in flight when the user data is cleared', async () => {
    const replies = []
    testApp.mock
      .onGet('/admin/templates/counts/')
      .reply(() => new Promise((resolve) => replies.push(resolve)))
    const { dispatch, getters } = testApp.store

    const before = dispatch('templatesAdmin/fetchCounts')
    await flushPromises()
    await dispatch('auth/clearAllStoreUserData')
    replies[0]([200, { in_review: 5, public: 0, rejected: 0 }])
    await before

    expect(getters['templatesAdmin/counts']).toBe(null)

    const after = dispatch('templatesAdmin/ensureCounts')
    await flushPromises()

    expect(replies).toHaveLength(2)
    replies[1]([200, { in_review: 2, public: 0, rejected: 0 }])
    await after
    expect(getters['templatesAdmin/inReviewCount']).toBe(2)
  })

  test('searches on the server without fetching the counts', async () => {
    const wrapper = await mountTable([row('in_review')])

    const input = wrapper.find('.data-table__header input')
    await input.setValue('ada')
    await flushPromises()

    expect(testApp.mock.history.get.at(-1)).toMatchObject({
      url: '/admin/templates/',
      params: { search: 'ada', state: 'in_review' },
    })
    expect(requestsTo('/admin/templates/counts/').length).toBe(1)
  })

  test.each([
    ['Ada', 'Ada', 'A'],
    ['', 'ada@example.com', 'A'],
  ])('names the author "%s" by %s', async (firstName, name, initial) => {
    const wrapper = await testApp.mount(TemplateAuthorField, {
      props: {
        row: {
          id: 3,
          author: { first_name: firstName, email: 'ada@example.com' },
        },
      },
    })

    expect(wrapper.find('.templates-admin-author__name').text()).toBe(name)
    expect(wrapper.find('.avatar__initials').text()).toBe(initial)
  })

  test('shows when a rejected template is listed', async () => {
    const wrapper = await testApp.mount(TemplateNameField, {
      props: {
        row: { id: 3, name: 'Sprint', state: 'rejected', listed: true },
      },
    })

    expect(wrapper.findAll('.badge').map((badge) => badge.text())).toEqual([
      'userTemplateList.stateListed',
    ])
  })
})
