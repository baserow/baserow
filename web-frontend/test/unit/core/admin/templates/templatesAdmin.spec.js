import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
import { TemplatesAdminType } from '@baserow/modules/core/adminTypes'
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import TemplateReviewActionsField from '@baserow/modules/core/components/admin/templates/fields/TemplateReviewActionsField'
import TemplateNameField from '@baserow/modules/core/components/admin/templates/fields/TemplateNameField'
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

  const mountField = (state, listed = false) =>
    testApp.mount(TemplateReviewActionsField, {
      props: { row: { id: 3, revision_id: 7, name: 'Sprint', state, listed } },
      global: { stubs: { Modal: ModalStub } },
    })

  const button = (wrapper, label) =>
    wrapper.findAll('button').find((button) => button.text() === label)

  test.each([
    ['public', ['templatesAdmin.reject']],
    ['in_review', ['templatesAdmin.reject', 'templatesAdmin.approve']],
    ['rejected', ['templatesAdmin.approve']],
    // Only its latest change was rejected, so it can still be unlisted.
    ['rejected', ['templatesAdmin.reject', 'templatesAdmin.approve'], true],
  ])('shows the actions of a %s template', async (state, labels, listed) => {
    const wrapper = await mountField(state, listed)

    expect(wrapper.findAll('button').map((button) => button.text())).toEqual(
      labels
    )
  })

  test('rejects with the trimmed reason once one is given', async () => {
    const row = { id: 3, revision_id: 7, state: 'rejected', reason: 'Spam' }
    testApp.mock.onPost('/admin/templates/3/reject/').reply(200, row)
    const wrapper = await mountField('public')
    await button(wrapper, 'templatesAdmin.reject').trigger('click')
    const submit = button(wrapper, 'rejectTemplateModal.reject')
    const input = wrapper.find('input')

    for (const reason of ['', '   ']) {
      await input.setValue(reason)
      expect(submit.attributes('disabled')).toBeDefined()
    }
    await input.setValue('  Spam ')
    await submit.trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      revision_id: 7,
      reason: 'Spam',
      state: 'public',
      listed: false,
    })
    // Refreshed, so that the template moves to the tab of its new state.
    expect(wrapper.emitted('refresh')).toHaveLength(1)
  })

  test.each([
    ['public', true, 'rejectTemplateModal.description'],
    ['in_review', true, 'rejectTemplateModal.editDescription'],
    // A first submission isn't listed, so rejecting it isn't about an edit.
    ['in_review', false, 'rejectTemplateModal.description'],
  ])(
    'tells what rejecting a %s template (listed: %s) does',
    async (state, listed, description) => {
      const wrapper = await mountField(state, listed)

      await button(wrapper, 'templatesAdmin.reject').trigger('click')

      expect(wrapper.find('p').text()).toBe(description)
    }
  )

  test('confirms a review that ends after its row is gone', async () => {
    let respond = null
    testApp.mock.onPost('/admin/templates/3/approve/').reply(
      () =>
        new Promise((resolve) => {
          respond = resolve
        })
    )
    const wrapper = await mountField('in_review')
    await button(wrapper, 'templatesAdmin.approve').trigger('click')
    await flushPromises()
    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      revision_id: 7,
      state: 'in_review',
      listed: false,
    })

    wrapper.unmount()
    respond([200, { id: 3, revision_id: 7, state: 'public' }])
    await flushPromises()

    expect(testApp.store.state.toast.items[0]).toMatchObject({
      type: 'success',
      title: 'templatesAdmin.approved',
    })
  })

  test.each([
    ['ERROR_TEMPLATE_UPDATED', 'templatesAdmin.changedTitle'],
    ['ERROR_TEMPLATE_ALREADY_APPROVED', 'templatesAdmin.alreadyApprovedTitle'],
    ['ERROR_TEMPLATE_ALREADY_REJECTED', 'templatesAdmin.alreadyRejectedTitle'],
  ])(
    'refreshes the list when the template changed (%s)',
    async (code, title) => {
      testApp.mock
        .onPost('/admin/templates/3/approve/')
        .reply(400, { error: code, detail: 'Changed.' })
      const wrapper = await mountField('in_review')

      await button(wrapper, 'templatesAdmin.approve').trigger('click')
      await flushPromises()

      expect(JSON.parse(testApp.mock.history.post[0].data).state).toBe(
        'in_review'
      )
      expect(testApp.store.state.toast.items[0]).toMatchObject({
        type: 'error',
        title,
      })
      expect(wrapper.emitted('refresh')).toHaveLength(1)
    }
  )
})
