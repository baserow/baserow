import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { TemplatesAdminType } from '@baserow/modules/core/adminTypes'
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import TemplateReviewActionsField from '@baserow/modules/core/components/admin/templates/fields/TemplateReviewActionsField'
import TemplateNameField from '@baserow/modules/core/components/admin/templates/fields/TemplateNameField'
import TemplateAuthorField from '@baserow/modules/core/components/admin/templates/fields/TemplateAuthorField'
import TemplatesAdminTable from '@baserow/modules/core/components/admin/templates/TemplatesAdminTable'

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
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('lists the templates of the chosen tab with its counts', async () => {
    const row = { id: 3, revision_id: 7, name: 'Sprint', author: null }
    testApp.mock
      .onGet('/admin/templates/')
      .reply(200, { count: 1, results: [{ ...row, reason: 'Spam' }] })
    testApp.mock
      .onGet('/admin/templates/counts/')
      .reply(200, { in_review: 4, public: 12, rejected: 2 })
    const wrapper = await testApp.mount(TemplatesAdminTable)
    await flushPromises()
    const listStates = () =>
      testApp.mock.history.get
        .filter((request) => request.url === '/admin/templates/')
        .map((request) => request.params.state)
    const countRequests = () =>
      testApp.mock.history.get.filter(
        (request) => request.url === '/admin/templates/counts/'
      ).length
    const headers = () =>
      wrapper.findAll('.data-table__table-cell--header').map((h) => h.text())

    expect(wrapper.find('.data-table__subtitle').text()).toBe(
      'templatesAdmin.subtitle'
    )
    expect(listStates()).toEqual(['in_review'])
    expect(countRequests()).toBe(1)
    expect(headers()).toContain('templatesAdmin.updatedOn')

    await wrapper.findAll('.tabs__item').at(2).trigger('click')
    await flushPromises()

    expect(listStates()).toEqual(['in_review', 'rejected'])
    expect(countRequests()).toBe(2)
    expect(headers()).toContain('templatesAdmin.reason')
    expect(headers()).not.toContain('templatesAdmin.updatedOn')
  })

  test('tells when the tab has no templates', async () => {
    testApp.mock
      .onGet('/admin/templates/')
      .reply(200, { count: 0, results: [] })
    testApp.mock
      .onGet('/admin/templates/counts/')
      .reply(200, { in_review: 0, public: 0, rejected: 0 })
    const wrapper = await testApp.mount(TemplatesAdminTable)
    await flushPromises()

    expect(wrapper.find('.data-table__empty').text()).toBe(
      'templatesAdmin.inReviewEmpty'
    )
  })

  const mountTable = async (rows, count = rows.length) => {
    testApp.mock.onGet('/admin/templates/').reply(200, { count, results: rows })
    testApp.mock
      .onGet('/admin/templates/counts/')
      .reply(200, { in_review: 1, public: 1, rejected: 0 })
    // The applications of the revision that the preview shows.
    testApp.mock.onGet('/applications/workspace/9/').reply(200, [])
    const wrapper = await testApp.mount(TemplatesAdminTable)
    await flushPromises()
    return wrapper
  }

  const countRequests = () =>
    testApp.mock.history.get.filter(
      (request) => request.url === '/admin/templates/counts/'
    ).length

  const listRequests = () =>
    testApp.mock.history.get.filter(
      (request) => request.url === '/admin/templates/'
    ).length

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

  const row = (state, listed = false) => ({
    id: 3,
    revision_id: 7,
    name: 'Sprint',
    state,
    listed,
    workspace_id: 9,
    author: { first_name: '', email: 'ada@example.com' },
  })

  // Opens the reject modal of the template: from its preview when it's in review
  // or rejected, from its row when it's published.
  const openReject = async (wrapper, template, action) => {
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
    // An edit of a listed template is rejected, not unlisted.
    ['in_review', true, ['templatesAdmin.reject', 'templatesAdmin.approve']],
    ['rejected', false, ['templatesAdmin.approve']],
    // Only its latest change was rejected, so it can still be unlisted.
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

  test.each([
    // The list shows that it worked, so only an error has a toast.
    [200, { ...row('public', true) }, []],
    // The template changed since the list was loaded.
    [
      400,
      { error: 'ERROR_TEMPLATE_UPDATED', detail: 'Changed.' },
      [{ type: 'error', title: 'templatesAdmin.changedTitle' }],
    ],
  ])(
    'approves from the preview (%s), then closes it and refreshes the list and counts',
    async (status, response, toasts) => {
      testApp.mock.onPost('/admin/templates/3/approve/').reply(status, response)
      const wrapper = await mountTable([row('in_review')], 150)

      // The counts don't change with the page of the list.
      await wrapper.find('.paginator__button:last-child').trigger('click')
      await flushPromises()
      expect(testApp.mock.history.get.at(-1).params.page).toBe(2)
      expect(countRequests()).toBe(1)

      await rowButton(wrapper, 'templatesAdmin.review').trigger('click')
      await flushPromises()
      bodyButton('templatesAdmin.approve').click()
      await flushPromises()

      expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
        revision_id: 7,
        state: 'in_review',
        listed: false,
      })
      expect(testApp.store.state.toast.items).toMatchObject(toasts)
      expect(listRequests()).toBe(3)
      expect(countRequests()).toBe(2)
      expect(document.body.classList.contains('prevent-scroll')).toBe(false)
      await new Promise((resolve) => setTimeout(resolve))
      expect(previewButtons()).toEqual([])
    }
  )

  test.each([
    ['in_review', false, 'reject'],
    // Unlisting is a reject of a listed template.
    ['public', true, 'unlist'],
    ['rejected', true, 'unlist'],
  ])(
    'rejects a %s template (listed: %s) with the trimmed reason, then refreshes',
    async (state, listed, action) => {
      const template = row(state, listed)
      testApp.mock
        .onPost('/admin/templates/3/reject/')
        .reply(200, { ...template, state: 'rejected', listed: false })
      const wrapper = await mountTable([template])

      await openReject(wrapper, template, action)
      expect(document.body.classList.contains('prevent-scroll')).toBe(true)
      const submit = () => bodyButton(`rejectTemplateModal.${action}`)
      const setReason = async (reason) => {
        const input = document.body.querySelector('.user-template-modal input')
        input.value = reason
        input.dispatchEvent(new Event('input'))
        await flushPromises()
      }
      for (const reason of ['', '   ']) {
        await setReason(reason)
        expect(submit().disabled).toBe(true)
      }
      await setReason('  Spam ')
      submit().click()
      await flushPromises()

      expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
        revision_id: 7,
        reason: 'Spam',
        state,
        listed,
      })
      expect(testApp.store.state.toast.items).toEqual([])
      // The refresh unmounts the rows, while the modals are the table's, so
      // they still hide and let the page scroll again.
      expect(listRequests()).toBe(2)
      expect(countRequests()).toBe(2)
      expect(document.body.classList.contains('prevent-scroll')).toBe(false)
      await new Promise((resolve) => setTimeout(resolve))
      expect(previewButtons()).toEqual([])
    }
  )

  test('closes only the reject modal on top of the preview with escape', async () => {
    const template = row('in_review')
    const wrapper = await mountTable([template])
    await openReject(wrapper, template, 'reject')

    window.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape' }))
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve))

    expect(document.body.querySelector('.user-template-modal')).toBeNull()
    expect(previewButtons()).toEqual([
      'templatesAdmin.reject',
      'templatesAdmin.approve',
    ])
  })

  test('tells an unlist that the template was unlisted meanwhile', async () => {
    testApp.mock.onPost('/admin/templates/3/reject/').reply(400, {
      error: 'ERROR_TEMPLATE_ALREADY_REJECTED',
      detail: 'Changed.',
    })
    const wrapper = await mountTable([row('public', true)])

    await rowButton(wrapper, 'templatesAdmin.unlist').trigger('click')
    const input = document.body.querySelector('.user-template-modal input')
    input.value = 'Spam'
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    bodyButton('rejectTemplateModal.unlist').click()
    await flushPromises()

    expect(testApp.store.state.toast.items[0]).toMatchObject({
      type: 'error',
      title: 'templatesAdmin.alreadyUnlistedTitle',
    })
  })

  test.each([
    ['public', true, 'unlist', 'unlistTitle', 'unlistDescription'],
    ['in_review', true, 'reject', 'title', 'editDescription'],
    // A first submission isn't listed, so rejecting it isn't about an edit.
    ['in_review', false, 'reject', 'title', 'description'],
  ])(
    'tells what rejecting a %s template (listed: %s) does',
    async (state, listed, action, title, description) => {
      const template = row(state, listed)
      const wrapper = await mountTable([template])

      await openReject(wrapper, template, action)

      const modal = document.body.querySelector('.user-template-modal')
      // The keyboard doesn't stay on the buttons behind the modal.
      expect(document.activeElement).toBe(modal.querySelector('input'))
      expect(modal.querySelector('h2').textContent).toBe(
        `rejectTemplateModal.${title}`
      )
      expect(modal.querySelector('p').textContent.trim()).toBe(
        `rejectTemplateModal.${description}`
      )
      expect(bodyButton(`rejectTemplateModal.${action}`)).toBeDefined()
    }
  )

  test.each([
    ['Ada', 'Ada', 'A'],
    // `createsuperuser` or a SAML login can leave the first name empty.
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
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each([
    ['public', true, ['templatesAdmin.unlist']],
    ['in_review', false, ['templatesAdmin.review']],
    ['in_review', true, ['templatesAdmin.review']],
    ['rejected', false, ['templatesAdmin.review']],
    ['rejected', true, ['templatesAdmin.review']],
  ])(
    'shows the actions of a %s template (listed: %s)',
    async (state, listed, labels) => {
      const wrapper = await testApp.mount(TemplateReviewActionsField, {
        props: { row: { id: 3, name: 'Sprint', state, listed } },
      })

      expect(wrapper.findAll('button').map((button) => button.text())).toEqual(
        labels
      )
    }
  )
})
