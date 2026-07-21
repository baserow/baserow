import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import ReportAbuseModal from '@baserow/modules/core/components/abuseReport/ReportAbuseModal'

const VALID_DESCRIPTION =
  'This page is used for phishing. It pretends to be the login page of ' +
  'another company and asks visitors to fill out their credentials.'

describe('ReportAbuseModal', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  async function mountAndFillForm(props = {}) {
    const wrapper = await testApp.mount(ReportAbuseModal, {
      propsData: {
        resourceType: 'database_view',
        identifier: 'test-slug',
        ...props,
      },
    })
    await wrapper.vm.show()
    await flushPromises()

    const inputs = wrapper.findAll('input')
    await inputs.at(0).setValue('John Doe')
    await inputs.at(1).setValue('john@example.com')
    await wrapper.find('textarea').setValue(VALID_DESCRIPTION)
    return wrapper
  }

  function getAbuseReportRequests() {
    return mockServer.mock.history.post.filter(
      (request) => request.url === '/abuse-reports/'
    )
  }

  test('submits the report and shows the success state', async () => {
    mockServer.mock.onPost('/abuse-reports/').reply(204)

    const wrapper = await mountAndFillForm({
      requestConfig: {
        headers: { 'Baserow-View-Authorization': 'JWT public-token' },
      },
    })
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    const requests = getAbuseReportRequests()
    expect(requests).toHaveLength(1)
    expect(JSON.parse(requests[0].data)).toEqual({
      resource_type: 'database_view',
      identifier: 'test-slug',
      name: 'John Doe',
      email: 'john@example.com',
      description: VALID_DESCRIPTION,
    })
    expect(requests[0].headers['Baserow-View-Authorization']).toBe(
      'JWT public-token'
    )
    expect(wrapper.html()).toContain('reportAbuseModal.successTitle')
    expect(wrapper.vm.loading).toBe(false)
  })

  test('shows a specific message when reporting is disabled', async () => {
    mockServer.mock.onPost('/abuse-reports/').reply(400, {
      error: 'ERROR_ABUSE_REPORTING_DISABLED',
      detail: 'Reporting abuse has been disabled.',
    })

    const wrapper = await mountAndFillForm()
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.html()).toContain('reportAbuseModal.reportingDisabledTitle')
    expect(wrapper.html()).not.toContain('reportAbuseModal.successTitle')
    expect(wrapper.vm.loading).toBe(false)
  })

  test('does not submit when the form is invalid', async () => {
    mockServer.mock.onPost('/abuse-reports/').reply(204)

    const wrapper = await testApp.mount(ReportAbuseModal, {
      propsData: {
        resourceType: 'database_view',
        identifier: 'test-slug',
      },
    })
    await wrapper.vm.show()
    await flushPromises()

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(getAbuseReportRequests()).toHaveLength(0)
  })
})
