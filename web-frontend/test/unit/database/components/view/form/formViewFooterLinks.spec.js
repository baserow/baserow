import { TestApp } from '@baserow/test/helpers/testApp'
import FormViewFooterLinks from '@baserow/modules/database/components/view/form/FormViewFooterLinks'

describe('FormViewFooterLinks', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  async function mountFooter(propsData = {}) {
    return await testApp.mount(FormViewFooterLinks, { propsData })
  }

  test('does not show the report link by default', async () => {
    const wrapper = await mountFooter()

    expect(wrapper.find('.form-view__report-abuse').exists()).toBe(false)
    expect(wrapper.find('.form-view__powered-by-baserow').exists()).toBe(true)
  })

  test('shows the report link when requested', async () => {
    const wrapper = await mountFooter({
      showReportAbuse: true,
      identifier: 'test-slug',
    })

    expect(wrapper.find('.form-view__report-abuse').exists()).toBe(true)
  })

  test('shows the report link when the logo is hidden', async () => {
    const wrapper = await mountFooter({
      showLogo: false,
      showReportAbuse: true,
      identifier: 'test-slug',
    })

    expect(wrapper.find('.form-view__report-abuse').exists()).toBe(true)
    expect(wrapper.find('.form-view__powered-by-baserow').exists()).toBe(false)
  })

  test('renders nothing when the logo is hidden and reporting is not requested', async () => {
    const wrapper = await mountFooter({ showLogo: false })

    expect(wrapper.find('.form-view__footer-links').exists()).toBe(false)
  })

  test('does not show the report link when reporting is disabled instance wide', async () => {
    testApp.store.commit('settings/SET_SETTINGS', {
      allow_reporting_abuse: false,
    })

    const wrapper = await mountFooter({
      showReportAbuse: true,
      identifier: 'test-slug',
    })

    expect(wrapper.find('.form-view__report-abuse').exists()).toBe(false)
  })
})
