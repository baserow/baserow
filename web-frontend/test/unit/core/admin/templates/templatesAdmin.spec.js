import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { heldBack } from '@baserow/test/helpers/heldBack'
import { TemplatesAdminType } from '@baserow/modules/core/adminTypes'
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import TemplateReviewActionsField from '@baserow/modules/core/components/admin/templates/fields/TemplateReviewActionsField'
import TemplateNameField from '@baserow/modules/core/components/admin/templates/fields/TemplateNameField'
import TemplateAuthorField from '@baserow/modules/core/components/admin/templates/fields/TemplateAuthorField'
import TemplatesAdminTable from '@baserow/modules/core/components/admin/templates/TemplatesAdminTable'

const REVIEW_FIELDS = {
  'in_review:false': { can_reject: true, reject_unlists: false },
  'in_review:true': { can_reject: true, reject_unlists: false },
  'public:true': { can_reject: true, reject_unlists: true },
  'rejected:false': { can_reject: false, reject_unlists: false },
  'rejected:true': { can_reject: true, reject_unlists: true },
}

const row = (state, listed = false, canApprove = true) => ({
  id: 3,
  revision_id: 7,
  name: 'Sprint',
  state,
  listed,
  can_approve: canApprove,
  ...REVIEW_FIELDS[`${state}:${listed}`],
  workspace_id: 9,
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
      counts = { in_review: 1, public: 1, rejected: 0 },
    } = {}
  ) => {
    testApp.mock.onGet('/admin/templates/').reply(200, { count, results: rows })
    testApp.mock.onGet('/admin/templates/counts/').reply(200, counts)
    testApp.mock.onGet('/applications/workspace/9/').reply(200, [])
    const wrapper = await testApp.mount(TemplatesAdminTable)
    await flushPromises()
    return wrapper
  }

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
      { counts: { in_review: 4, public: 12, rejected: 2 } }
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
    expect(headers()).toContain('templatesAdmin.updatedOn')

    await wrapper.findAll('.tabs__item').at(2).trigger('click')
    await flushPromises()

    expect(listStates()).toEqual(['in_review', 'rejected'])
    expect(requestsTo('/admin/templates/counts/').length).toBe(2)
    expect(headers()).toContain('templatesAdmin.reason')
    expect(headers()).not.toContain('templatesAdmin.updatedOn')
  })

  test('shows the counts of the latest request only', async () => {
    const wrapper = await mountTable([])
    const older = heldBack()
    const newer = heldBack()
    const chooseTab = async (index, reply) => {
      testApp.mock.onGet('/admin/templates/counts/').reply(reply)
      await wrapper.findAll('.tabs__item').at(index).trigger('click')
      await flushPromises()
    }

    await chooseTab(1, older.reply)
    await chooseTab(2, newer.reply)
    newer.send([200, { in_review: 0, public: 0, rejected: 3 }])
    older.send([200, { in_review: 1, public: 1, rejected: 0 }])
    await flushPromises()

    expect(wrapper.findAll('.tabs__item').map((tab) => tab.text())).toEqual([
      'templatesAdmin.tabCount - 0',
      'templatesAdmin.tabCount - 0',
      'templatesAdmin.tabCount - 3',
    ])
  })

  test('tells when the tab has no templates', async () => {
    const wrapper = await mountTable([], {
      counts: { in_review: 0, public: 0, rejected: 0 },
    })

    expect(wrapper.find('.data-table__empty').text()).toBe(
      'templatesAdmin.inReviewEmpty'
    )
  })

  const clickAction = async (wrapper, template, action) => {
    if (template.state === 'public') {
      await rowButton(wrapper, `templatesAdmin.${action}`).trigger('click')
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
  ])(
    'tells that the template changed when the %s fails, then refreshes',
    async (action, template, error, title) => {
      const endpoint = action === 'approve' ? 'approve' : 'reject'
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

describe('TemplateReviewActionsField', () => {
  test.each([
    ['public', true, ['templatesAdmin.unlist']],
    ['in_review', false, ['templatesAdmin.review']],
    ['rejected', true, ['templatesAdmin.review']],
  ])(
    'shows the actions of a %s template (listed: %s)',
    async (state, listed, labels) => {
      const wrapper = await testApp.mount(TemplateReviewActionsField, {
        props: { row: row(state, listed) },
      })

      expect(wrapper.findAll('button').map((button) => button.text())).toEqual(
        labels
      )
    }
  )
})
