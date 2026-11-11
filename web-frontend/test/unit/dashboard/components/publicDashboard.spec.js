import { mount } from '@vue/test-utils'

import PublicDashboard from '@baserow/modules/dashboard/components/PublicDashboard'

function mountPublicDashboard({
  dashboard = {},
  isEmpty = false,
  loading = false,
  settings = {},
  publicSlug = 'conversion-compass',
  publicAuthToken = null,
} = {}) {
  return mount(PublicDashboard, {
    props: {
      dashboard: {
        id: 1,
        name: 'Conversion compass',
        description: 'Tracking conversion rates at every stage.',
        show_logo: true,
        workspace: { id: 0 },
        ...dashboard,
      },
      loading,
    },
    global: {
      mocks: {
        $t: (key) => key,
      },
      provide: {
        store: {
          getters: {
            'dashboardApplication/isEmpty': isEmpty,
            'dashboardApplication/getPublicSlug': publicSlug,
            'dashboardApplication/getPublicAuthToken': publicAuthToken,
            'settings/get': settings,
          },
        },
      },
      stubs: {
        WidgetBoard: {
          template: '<div data-testid="widget-board"></div>',
        },
        DashboardWidgetGridLoading: {
          template: '<div data-testid="widget-grid-loading"></div>',
        },
        ExternalLinkBaserowLogo: {
          template: '<a data-testid="baserow-logo"></a>',
        },
        ReportAbuseModal: {
          props: ['resourceType', 'identifier', 'requestConfig'],
          data() {
            return { shown: false }
          },
          methods: {
            show() {
              this.shown = true
            },
          },
          template: `
            <div
              data-testid="report-abuse-modal"
              :data-shown="shown"
              :data-resource-type="resourceType"
              :data-identifier="identifier"
              :data-authorization="requestConfig.headers?.['Baserow-Dashboard-Authorization'] || ''"
            ></div>
          `,
        },
      },
    },
  })
}

describe('PublicDashboard', () => {
  test('shows the name, the description, the widgets and the Baserow logo', () => {
    const wrapper = mountPublicDashboard()

    expect(wrapper.get('.dashboard-app__title').text()).toBe(
      'Conversion compass'
    )
    expect(wrapper.get('.dashboard-app__description').text()).toBe(
      'Tracking conversion rates at every stage.'
    )
    expect(wrapper.find('[data-testid="widget-board"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="baserow-logo"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="widget-grid-loading"]').exists()).toBe(
      false
    )
  })

  test('hides the Baserow logo when the owner switched it off', () => {
    const wrapper = mountPublicDashboard({ dashboard: { show_logo: false } })

    expect(wrapper.find('[data-testid="baserow-logo"]').exists()).toBe(false)
  })

  test('leaves out an empty description', () => {
    const wrapper = mountPublicDashboard({ dashboard: { description: '' } })

    expect(wrapper.find('.dashboard-app__description').exists()).toBe(false)
  })

  test('shows the loading state instead of the widgets while loading', () => {
    const wrapper = mountPublicDashboard({ loading: true })

    expect(wrapper.find('[data-testid="widget-grid-loading"]').exists()).toBe(
      true
    )
    expect(wrapper.find('[data-testid="widget-board"]').exists()).toBe(false)
  })

  test('tells visitors when the dashboard has no widgets', () => {
    const wrapper = mountPublicDashboard({ isEmpty: true })

    expect(wrapper.get('.public-dashboard__empty').text()).toBe(
      'publicDashboard.noWidgets'
    )
    expect(wrapper.find('[data-testid="widget-board"]').exists()).toBe(false)
  })

  test('lets visitors report the dashboard for abuse', async () => {
    const wrapper = mountPublicDashboard()

    const link = wrapper.get('.public-dashboard__report-abuse')
    expect(link.text()).toBe('publicDashboard.reportAbuse')
    const modal = wrapper.get('[data-testid="report-abuse-modal"]')
    expect(modal.attributes('data-resource-type')).toBe('dashboard')
    expect(modal.attributes('data-identifier')).toBe('conversion-compass')
    expect(modal.attributes('data-authorization')).toBe('')
    expect(modal.attributes('data-shown')).toBe('false')

    await link.trigger('click')

    expect(modal.attributes('data-shown')).toBe('true')
  })

  test('sends the password token along with the abuse report', () => {
    const wrapper = mountPublicDashboard({ publicAuthToken: 'secret-token' })

    expect(
      wrapper
        .get('[data-testid="report-abuse-modal"]')
        .attributes('data-authorization')
    ).toBe('JWT secret-token')
  })

  test('keeps the report link when the logo is hidden', () => {
    const wrapper = mountPublicDashboard({ dashboard: { show_logo: false } })

    expect(wrapper.find('.public-dashboard__footer').exists()).toBe(true)
    expect(wrapper.find('.public-dashboard__report-abuse').exists()).toBe(true)
    expect(wrapper.find('[data-testid="baserow-logo"]').exists()).toBe(false)
  })

  test('hides the report link when reporting is disabled instance wide', () => {
    const wrapper = mountPublicDashboard({
      settings: { allow_reporting_abuse: false },
    })

    expect(wrapper.find('.public-dashboard__report-abuse').exists()).toBe(false)
    expect(wrapper.find('[data-testid="report-abuse-modal"]').exists()).toBe(
      false
    )
    expect(wrapper.find('[data-testid="baserow-logo"]').exists()).toBe(true)
  })

  test('renders no footer when the logo is hidden and reporting is disabled', () => {
    const wrapper = mountPublicDashboard({
      dashboard: { show_logo: false },
      settings: { allow_reporting_abuse: false },
    })

    expect(wrapper.find('.public-dashboard__footer').exists()).toBe(false)
  })
})
