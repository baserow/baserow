import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import ShareDashboardLink from '@baserow/modules/dashboard/components/sharing/ShareDashboardLink'
import DashboardRotateSlugModal from '@baserow/modules/dashboard/components/sharing/DashboardRotateSlugModal'
import DashboardEnablePasswordModal from '@baserow/modules/dashboard/components/sharing/DashboardEnablePasswordModal'
import DashboardDisablePasswordModal from '@baserow/modules/dashboard/components/sharing/DashboardDisablePasswordModal'
import Context from '@baserow/modules/core/components/Context'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

vi.mock(
  '@baserow/modules/database/utils/clipboard',
  async (importOriginal) => ({
    ...(await importOriginal()),
    copyToClipboard: vi.fn(),
  })
)

const DASHBOARD_ID = 10

describe('ShareDashboardLink', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.getStore()
  })

  afterEach(() => testApp.afterEach())

  async function createDashboard(values = {}) {
    const workspace = { id: 1, name: 'Workspace' }
    await store.dispatch('workspace/forceCreate', workspace)
    await store.dispatch('application/forceCreate', {
      id: DASHBOARD_ID,
      type: 'dashboard',
      name: 'Conversion compass',
      workspace,
      public: false,
      slug: 'dashboard-slug',
      public_has_password: false,
      show_logo: true,
      ...values,
    })
    return store.getters['application/get'](DASHBOARD_ID)
  }

  async function openContext(dashboard) {
    const wrapper = await testApp.mount(ShareDashboardLink, {
      props: { dashboard },
      // The context and the modals teleport their content into the body. The
      // globally stubbed teleport remounts that content on every re-render of
      // the context, which also replaces the element its click outside handler
      // watches, so a click inside the context would close it.
      global: { stubs: { Teleport: false } },
    })
    await wrapper.find('.header__filter-link').trigger('click')
    const context = wrapper.findComponent(Context)
    expect(context.vm.isOpen()).toBe(true)
    return { wrapper, context: teleported(context) }
  }

  /**
   * The content of a context or modal lives in the body, outside of the
   * component's own element.
   */
  function teleported(component) {
    return new DOMWrapper(component.vm.getTeleportedElement())
  }

  function findButtonByText(wrapper, text) {
    return wrapper
      .findAll('button')
      .filter((button) => button.text().includes(text))
      .at(0)
  }

  function findPasswordOption(context) {
    return context
      .findAll('.dashboard-sharing__option')
      .filter(
        (option) =>
          option.text().includes('shareDashboardLink.restrictWithPassword') ||
          option.text().includes('shareDashboardLink.passwordProtected')
      )
      .at(0)
  }

  function expectedShareUrl(slug) {
    const { baserowEmbeddedShareUrl } = testApp.getApp().$config.public
    return `${baserowEmbeddedShareUrl}/public/dashboard/${slug}`
  }

  test('creates a private link for a dashboard that is not shared yet', async () => {
    const dashboard = await createDashboard()
    testApp.mock
      .onPatch(`/dashboard/${DASHBOARD_ID}/sharing/`, { public: true })
      .reply(200, { id: DASHBOARD_ID, type: 'dashboard', public: true })

    const { context } = await openContext(dashboard)

    expect(context.text()).toContain('shareDashboardLink.notSharedTitle')
    expect(context.find('.dashboard-sharing__shared-link-box').exists()).toBe(
      false
    )

    await findButtonByText(
      context,
      'shareDashboardLink.createPrivateLink'
    ).trigger('click')
    await flushPromises()

    expect(store.getters['application/get'](DASHBOARD_ID).public).toBe(true)
    expect(context.text()).toContain('shareDashboardLink.sharedTitle')
    expect(context.find('.dashboard-sharing__shared-link-box').text()).toBe(
      expectedShareUrl('dashboard-slug')
    )
  })

  test('shows the public URL and copies it to the clipboard', async () => {
    const dashboard = await createDashboard({ public: true })

    const { context } = await openContext(dashboard)

    expect(context.find('.dashboard-sharing__shared-link-box').text()).toBe(
      expectedShareUrl('dashboard-slug')
    )

    await context
      .findAll('.dashboard-sharing__shared-link-action')
      .at(0)
      .trigger('click')

    expect(copyToClipboard).toHaveBeenCalledWith(
      expectedShareUrl('dashboard-slug')
    )
    expect(context.find('.copied--show').exists()).toBe(true)
  })

  test('disables the shared link', async () => {
    const dashboard = await createDashboard({ public: true })
    testApp.mock
      .onPatch(`/dashboard/${DASHBOARD_ID}/sharing/`, { public: false })
      .reply(200, { id: DASHBOARD_ID, type: 'dashboard', public: false })

    const { context } = await openContext(dashboard)

    await findButtonByText(context, 'shareDashboardLink.disableLink').trigger(
      'click'
    )
    await flushPromises()

    expect(store.getters['application/get'](DASHBOARD_ID).public).toBe(false)
    expect(context.text()).toContain('shareDashboardLink.notSharedTitle')
    expect(context.find('.dashboard-sharing__shared-link-box').exists()).toBe(
      false
    )
  })

  test('rotates the slug after confirmation and shows a success toast', async () => {
    const dashboard = await createDashboard({ public: true })
    testApp.mock.onPost(`/dashboard/${DASHBOARD_ID}/rotate-slug/`).reply(200, {
      id: DASHBOARD_ID,
      type: 'dashboard',
      public: true,
      slug: 'rotated-slug',
    })

    const { wrapper, context } = await openContext(dashboard)

    await context
      .findAll('.dashboard-sharing__shared-link-action')
      .at(1)
      .trigger('click')

    const modal = teleported(wrapper.findComponent(DashboardRotateSlugModal))
    expect(modal.text()).toContain('dashboardRotateSlugModal.title')
    expect(store.getters['application/get'](DASHBOARD_ID).slug).toBe(
      'dashboard-slug'
    )

    await findButtonByText(
      modal,
      'dashboardRotateSlugModal.generateNewUrl'
    ).trigger('click')
    await flushPromises()

    expect(store.getters['application/get'](DASHBOARD_ID).slug).toBe(
      'rotated-slug'
    )
    expect(context.find('.dashboard-sharing__shared-link-box').text()).toBe(
      expectedShareUrl('rotated-slug')
    )
    expect(store.state.toast.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: 'success',
          title: 'dashboardRotateSlugModal.success',
        }),
      ])
    )
  })

  test('keeps the slug when the rotation is cancelled', async () => {
    const dashboard = await createDashboard({ public: true })

    const { wrapper, context } = await openContext(dashboard)

    await context
      .findAll('.dashboard-sharing__shared-link-action')
      .at(1)
      .trigger('click')

    const modal = teleported(wrapper.findComponent(DashboardRotateSlugModal))
    await findButtonByText(modal, 'action.cancel').trigger('click')
    await flushPromises()

    expect(store.getters['application/get'](DASHBOARD_ID).slug).toBe(
      'dashboard-slug'
    )
    expect(store.state.toast.items).toHaveLength(0)
  })

  test('protects the link with a password after it was entered', async () => {
    const dashboard = await createDashboard({ public: true })
    testApp.mock
      .onPatch(`/dashboard/${DASHBOARD_ID}/sharing/`, {
        public_password: 'secret-password',
      })
      .reply(200, {
        id: DASHBOARD_ID,
        type: 'dashboard',
        public: true,
        public_has_password: true,
      })

    const { wrapper, context } = await openContext(dashboard)
    const option = findPasswordOption(context)
    expect(option.text()).toContain('shareDashboardLink.restrictWithPassword')
    expect(
      context.find('.dashboard-sharing__option-change-password').exists()
    ).toBe(false)

    await option.find('.switch').trigger('click')

    const modal = teleported(
      wrapper.findComponent(DashboardEnablePasswordModal)
    )
    expect(modal.text()).toContain('dashboardEnablePasswordModal.title')

    await modal.find('input').setValue('secret-password')
    await modal.find('form').trigger('submit')
    await flushPromises()

    expect(
      store.getters['application/get'](DASHBOARD_ID).public_has_password
    ).toBe(true)
    expect(findPasswordOption(context).text()).toContain(
      'shareDashboardLink.passwordProtected'
    )
    expect(
      context.find('.dashboard-sharing__option-change-password').exists()
    ).toBe(true)
  })

  test('protects the link with a password when Enter is pressed', async () => {
    const dashboard = await createDashboard({ public: true })
    testApp.mock
      .onPatch(`/dashboard/${DASHBOARD_ID}/sharing/`, {
        public_password: 'secret-password',
      })
      .reply(200, {
        id: DASHBOARD_ID,
        type: 'dashboard',
        public: true,
        public_has_password: true,
      })

    const { wrapper, context } = await openContext(dashboard)
    await findPasswordOption(context).find('.switch').trigger('click')

    const modal = teleported(
      wrapper.findComponent(DashboardEnablePasswordModal)
    )
    await modal.find('input').setValue('secret-password')

    // Pressing Enter in the input activates the first submit button of the
    // form, which jsdom doesn't simulate, so that button is clicked instead.
    const defaultButton = modal
      .findAll('form button')
      .filter((button) => button.element.type === 'submit')
      .at(0)
    expect(defaultButton.text()).toContain(
      'dashboardEnablePasswordModal.setPassword'
    )
    await defaultButton.trigger('click')
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(1)
    expect(
      store.getters['application/get'](DASHBOARD_ID).public_has_password
    ).toBe(true)
  })

  test('does not send a password shorter than 8 characters', async () => {
    const dashboard = await createDashboard({ public: true })

    const { wrapper, context } = await openContext(dashboard)
    await findPasswordOption(context).find('.switch').trigger('click')

    const modal = teleported(
      wrapper.findComponent(DashboardEnablePasswordModal)
    )
    await modal.find('input').setValue('short')
    await modal.find('form').trigger('submit')
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(0)
    expect(modal.text()).toContain('error.minLength')
    expect(
      store.getters['application/get'](DASHBOARD_ID).public_has_password
    ).toBe(false)
  })

  test('changes the password from the pencil icon', async () => {
    const dashboard = await createDashboard({
      public: true,
      public_has_password: true,
    })
    testApp.mock
      .onPatch(`/dashboard/${DASHBOARD_ID}/sharing/`, {
        public_password: 'another-password',
      })
      .reply(200, {
        id: DASHBOARD_ID,
        type: 'dashboard',
        public: true,
        public_has_password: true,
      })

    const { wrapper, context } = await openContext(dashboard)
    await context
      .find('.dashboard-sharing__option-change-password')
      .trigger('click')

    const modal = teleported(
      wrapper.findComponent(DashboardEnablePasswordModal)
    )
    expect(modal.text()).toContain('dashboardEnablePasswordModal.changeTitle')

    await modal.find('input').setValue('another-password')
    await modal.find('form').trigger('submit')
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(1)
    expect(
      store.getters['application/get'](DASHBOARD_ID).public_has_password
    ).toBe(true)
  })

  test('removes the password after confirmation', async () => {
    const dashboard = await createDashboard({
      public: true,
      public_has_password: true,
    })
    testApp.mock
      .onPatch(`/dashboard/${DASHBOARD_ID}/sharing/`, { public_password: '' })
      .reply(200, {
        id: DASHBOARD_ID,
        type: 'dashboard',
        public: true,
        public_has_password: false,
      })

    const { wrapper, context } = await openContext(dashboard)
    const option = findPasswordOption(context)
    expect(option.text()).toContain('shareDashboardLink.passwordProtected')

    await option.find('.switch').trigger('click')

    const modal = teleported(
      wrapper.findComponent(DashboardDisablePasswordModal)
    )
    expect(modal.text()).toContain('dashboardDisablePasswordModal.title')

    await findButtonByText(
      modal,
      'dashboardDisablePasswordModal.disable'
    ).trigger('click')
    await flushPromises()

    expect(
      store.getters['application/get'](DASHBOARD_ID).public_has_password
    ).toBe(false)
    expect(findPasswordOption(context).text()).toContain(
      'shareDashboardLink.restrictWithPassword'
    )
  })

  test('keeps the password when the removal is cancelled', async () => {
    const dashboard = await createDashboard({
      public: true,
      public_has_password: true,
    })

    const { wrapper, context } = await openContext(dashboard)
    await findPasswordOption(context).find('.switch').trigger('click')

    const modal = teleported(
      wrapper.findComponent(DashboardDisablePasswordModal)
    )
    await findButtonByText(modal, 'action.cancel').trigger('click')
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(0)
    expect(
      store.getters['application/get'](DASHBOARD_ID).public_has_password
    ).toBe(true)
  })

  test('forgets the password when the shared link is disabled', async () => {
    const dashboard = await createDashboard({
      public: true,
      public_has_password: true,
    })
    // Disabling the link also removes the password on the backend, which the
    // response reports.
    testApp.mock
      .onPatch(`/dashboard/${DASHBOARD_ID}/sharing/`, { public: false })
      .reply(200, {
        id: DASHBOARD_ID,
        type: 'dashboard',
        public: false,
        public_has_password: false,
      })

    const { context } = await openContext(dashboard)
    await findButtonByText(context, 'shareDashboardLink.disableLink').trigger(
      'click'
    )
    await flushPromises()

    const updated = store.getters['application/get'](DASHBOARD_ID)
    expect(updated.public).toBe(false)
    expect(updated.public_has_password).toBe(false)
  })
})
