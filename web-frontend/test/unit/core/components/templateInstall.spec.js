import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

import { TestApp } from '@baserow/test/helpers/testApp'
import { permission } from '@baserow/test/helpers/permission'
import { updateJob } from '@baserow/test/helpers/store'
import TemplateInstall from '@baserow/modules/core/components/template/TemplateInstall'
import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import { workspaceSidebarVisibleKey } from '@baserow/modules/core/composables/useWorkspaceSidebar'

vi.mock('#app', async (importOriginal) =>
  (await import('@baserow/test/helpers/permission')).mockHasPermission(
    importOriginal
  )
)

const template = { id: 5, slug: 'project-tracker', name: 'Project Tracker' }

// What the `app` layout provides to the page and its toasts: whether its sidebar
// lists the selected workspace.
const withWorkspaceSidebar = (sidebar) => ({
  provide: { [workspaceSidebarVisibleKey]: sidebar },
})

describe('TemplateInstall', () => {
  let testApp = null
  let push = null

  beforeEach(() => {
    testApp = new TestApp()
    push = vi.spyOn(testApp.nuxtApp.$router, 'push').mockResolvedValue()
  })

  afterEach(async () => {
    permission.check = () => true
    push.mockRestore()
    await testApp.afterEach()
  })

  const signIn = () => {
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    testApp.store.dispatch('workspace/forceCreate', { id: 1, name: 'First' })
    testApp.store.dispatch('workspace/forceCreate', { id: 2, name: 'Second' })
  }

  const mockInstall = (workspaceId) =>
    testApp.mock
      .onPost(`/templates/install/${workspaceId}/${template.id}/async/`)
      .reply(202, { id: 10, type: 'install_template', state: 'finished' })

  const clickUse = async (wrapper) => {
    await wrapper.find('.template-install__use').trigger('click')
    await flushPromises()
  }

  test('sends an anonymous visitor to the login page and back', async () => {
    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template },
    })

    expect(wrapper.find('.template-install__workspace').exists()).toBe(false)

    await clickUse(wrapper)

    expect(push).toHaveBeenCalledWith({
      name: 'login',
      query: { original: '/template/project-tracker' },
    })
    expect(testApp.mock.history.post).toHaveLength(0)
    expect(wrapper.emitted('installed')).toBeUndefined()
  })

  test.each([
    [
      'installs into the provided workspace without redirecting',
      { workspace: { id: 2 } },
      2,
      // The public revision, or the owner's latest one while it isn't public.
      {},
    ],
    [
      'installs the latest revision when asked to',
      { workspace: { id: 2 }, latest: true },
      2,
      { latest: true },
    ],
    ['installs into the first workspace without leaving the page', {}, 1, {}],
  ])('%s', async (_title, props, workspaceId, params) => {
    signIn()
    mockInstall(workspaceId)

    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template, ...props },
    })
    await clickUse(wrapper)

    expect(testApp.mock.history.post.map((r) => r.url)).toStrictEqual([
      `/templates/install/${workspaceId}/5/async/`,
    ])
    expect(testApp.mock.history.post.map((r) => r.params)).toStrictEqual([
      params,
    ])
    expect(wrapper.emitted('installed')).toHaveLength(1)
    expect(push).not.toHaveBeenCalled()
    expect(
      wrapper.find('.template-install__use').attributes('disabled')
    ).toBeUndefined()
  })

  test('disables the workspaces the user cannot add applications to', async () => {
    signIn()
    permission.check = (operation, context, workspaceId) =>
      operation !== 'workspace.create_application' || workspaceId !== 1
    mockInstall(2)

    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template },
    })
    await flushPromises()

    const items = wrapper.findAllComponents({ name: 'DropdownItem' })
    expect(items.map((item) => item.props('disabled'))).toStrictEqual([
      true,
      false,
    ])
    expect(items[0].props('description')).toBe(
      'templateInstall.workspaceNoPermission'
    )

    // The first workspace the template can be installed into is preselected.
    await clickUse(wrapper)

    expect(testApp.mock.history.post.map((r) => r.url)).toStrictEqual([
      '/templates/install/2/5/async/',
    ])
  })

  test('cannot install without a workspace to add applications to', async () => {
    signIn()
    permission.check = (operation) =>
      operation !== 'workspace.create_application'

    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template, workspace: { id: 1 } },
    })
    await flushPromises()

    expect(
      wrapper.find('.template-install__use').attributes('disabled')
    ).toBeDefined()
  })

  const installToasts = () =>
    testApp.store.state.toast.items.filter(
      (toast) => toast.type === 'installTemplate'
    )

  const selectWorkspace = (id) =>
    testApp.store.commit(
      'workspace/SET_SELECTED',
      testApp.store.getters['workspace/get'](id)
    )

  describe('while the install runs', () => {
    const mockRunningInstall = (workspaceId) =>
      testApp.mock
        .onPost(`/templates/install/${workspaceId}/${template.id}/async/`)
        .reply(202, {
          id: 10,
          type: 'install_template',
          state: 'started',
          progress_percentage: 10,
          workspace: { id: workspaceId },
          installed_applications: [],
          human_readable_error: '',
        })

    // The page and the toasts of the `app` layout, which share its sidebar.
    const startInstall = async (workspaceId, sidebar) => {
      const global = withWorkspaceSidebar(sidebar)
      const toasts = await testApp.mount(Toasts, { global })
      const wrapper = await testApp.mount(TemplateInstall, {
        props: { template, workspace: { id: workspaceId } },
        global,
      })
      await clickUse(wrapper)
      return toasts
    }

    const shownInstallToasts = (toasts) =>
      toasts.findAll('.install-template-toast')

    test('hides the progress while the sidebar shows the target workspace, then shows the result', async () => {
      signIn()
      selectWorkspace(1)
      mockRunningInstall(1)

      const toasts = await startInstall(1, ref(true))

      expect(installToasts()).toHaveLength(1)
      expect(shownInstallToasts(toasts)).toHaveLength(0)

      await updateJob(testApp.store, 10, {
        state: 'finished',
        installed_applications: [],
      })

      expect(shownInstallToasts(toasts)).toHaveLength(1)
      expect(toasts.find('.toast__title').text()).toBe(
        'InstallTemplateJobType.installedMessage'
      )
    })

    test.each([
      [
        'shows the progress when the sidebar is collapsed during the install',
        (sidebar) => {
          sidebar.value = false
        },
      ],
      [
        'shows the progress when the user switches workspace during the install',
        () => selectWorkspace(2),
      ],
    ])('%s', async (_title, leaveWorkspace) => {
      signIn()
      selectWorkspace(1)
      mockRunningInstall(1)
      const sidebar = ref(true)
      const toasts = await startInstall(1, sidebar)

      leaveWorkspace(sidebar)
      await flushPromises()

      expect(shownInstallToasts(toasts)).toHaveLength(1)
      expect(toasts.find('.toast__message').text()).toBe('10 %')
    })
  })

  test('shows the copy link only when asked', async () => {
    let wrapper = await testApp.mount(TemplateInstall, {
      props: { template },
    })
    await wrapper
      .find('.template-install__actions .button-icon')
      .trigger('click')
    expect(wrapper.findAll('.context__menu-item-link')).toHaveLength(1)

    wrapper = await testApp.mount(TemplateInstall, {
      props: { template, showCopyLink: false },
    })
    await wrapper
      .find('.template-install__actions .button-icon')
      .trigger('click')
    expect(wrapper.findAll('.context__menu-item-link')).toHaveLength(0)
  })

  test('does not report a failed install as installed', async () => {
    signIn()
    testApp.dontFailOnErrorResponses()
    testApp.mock
      .onPost(`/templates/install/1/${template.id}/async/`)
      .reply(400, { error: 'ERROR_USER_NOT_IN_GROUP' })

    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template, workspace: { id: 1 } },
    })
    await clickUse(wrapper)

    expect(wrapper.emitted('installed')).toBeUndefined()
    expect(push).not.toHaveBeenCalled()
    expect(installToasts()).toHaveLength(0)
    expect(
      wrapper.find('.template-install__use').attributes('disabled')
    ).toBeUndefined()
  })

  test('tells the user and asks to reload when the template was updated', async () => {
    signIn()
    testApp.dontFailOnErrorResponses()
    testApp.mock
      .onPost(`/templates/install/1/${template.id}/async/`)
      .reply(400, {
        error: 'ERROR_TEMPLATE_UPDATED',
        detail: 'The template was updated after it was opened.',
      })

    const wrapper = await testApp.mount(TemplateInstall, {
      props: {
        template: { ...template, revision_id: 8 },
        workspace: { id: 1 },
      },
    })
    await clickUse(wrapper)

    expect(
      testApp.store.state.toast.items.map((toast) => [toast.type, toast.title])
    ).toStrictEqual([['error', 'clientHandler.templateUpdatedTitle']])
    expect(wrapper.emitted('outdated')).toHaveLength(1)
    expect(wrapper.emitted('installed')).toBeUndefined()
    expect(installToasts()).toHaveLength(0)
  })

  describe('download', () => {
    const userTemplate = {
      id: 5,
      type: 'user',
      slug: 'crm-a1b2c3',
      name: 'CRM',
    }
    const runningJob = () => ({
      id: 20,
      type: 'download_user_template',
      state: 'pending',
      progress_percentage: 0,
      human_readable_error: '',
      url: null,
      file_name: 'crm.zip',
    })

    // The copied label is left out of the texts of the menu.
    const mountWithMenu = async (props, { mocks = {} } = {}) => {
      const wrapper = await testApp.mount(TemplateInstall, {
        props,
        global: { mocks, stubs: { Copied: true } },
      })
      await flushPromises()
      await wrapper
        .find('.template-install__actions .button-icon')
        .trigger('click')
      await flushPromises()
      return wrapper
    }

    const menuTexts = (wrapper) =>
      wrapper.findAll('.context__menu-item-link').map((link) => link.text())

    const downloadLink = (wrapper) =>
      wrapper
        .findAll('.context__menu-item-link')
        .find((link) => link.text() === 'templateInstall.download')

    // The click doesn't bubble, so that only the item handles it. In the tests the
    // menu is rendered again with a new element, which its check of the clicks
    // outside of it would take as one.
    const clickDownload = async (wrapper) => {
      downloadLink(wrapper).element.dispatchEvent(
        new MouseEvent('click', { bubbles: false, cancelable: true })
      )
      await flushPromises()
    }

    const menuIsOpen = (wrapper) =>
      wrapper.findComponent({ name: 'Context' }).vm.isOpen()

    const downloadRequests = () =>
      testApp.mock.history.post
        .filter((request) => request.url === '/jobs/')
        .map((request) => JSON.parse(request.data))

    const downloadToasts = () =>
      testApp.store.state.toast.items.filter(
        (toast) => toast.type === 'downloadTemplate'
      )

    const errorToasts = () =>
      testApp.store.state.toast.items.filter((toast) => toast.type === 'error')

    test.each([
      ['a user template', userTemplate, true, ['download']],
      ['an official template', template, true, []],
      ['a user template while user templates are off', userTemplate, false, []],
    ])('menu of %s', async (_, shown, flag, extra) => {
      signIn()
      const wrapper = await mountWithMenu(
        { template: shown },
        { mocks: { $featureFlagIsEnabled: () => flag } }
      )

      expect(menuTexts(wrapper)).toStrictEqual([
        'templateInstall.copyLink',
        ...extra.map((item) => `templateInstall.${item}`),
      ])
    })

    test.each([false, true])(
      'starts the download job with its toast, then closes the menu (latest: %s)',
      async (latest) => {
        signIn()
        let reply = null
        testApp.mock.onPost('/jobs/').reply(
          () =>
            new Promise((resolve) => {
              reply = resolve
            })
        )
        const wrapper = await mountWithMenu({ template: userTemplate, latest })

        await clickDownload(wrapper)

        // While the job is requested the item shows it, and the menu stays open.
        expect(downloadLink(wrapper).classes()).toContain(
          'context__menu-item-link--loading'
        )
        expect(menuIsOpen(wrapper)).toBe(true)

        // A second click doesn't request it again.
        await clickDownload(wrapper)
        expect(downloadRequests()).toStrictEqual([
          { type: 'download_user_template', slug: 'crm-a1b2c3', latest },
        ])

        reply([200, runningJob()])
        await flushPromises()

        expect(downloadToasts().map((toast) => toast.data)).toStrictEqual([
          {
            jobId: 20,
            template_name: 'CRM',
            slug: 'crm-a1b2c3',
            latest,
            autoDownload: true,
          },
        ])
        expect(menuIsOpen(wrapper)).toBe(false)
      }
    )

    test('shows why a template is not downloaded', async () => {
      signIn()
      testApp.dontFailOnErrorResponses()
      testApp.mock.onPost('/jobs/').reply(400, {
        error: 'ERROR_TEMPLATE_BLOCKED',
        detail: 'The template is blocked.',
      })
      const wrapper = await mountWithMenu({ template: userTemplate })

      await clickDownload(wrapper)

      expect(errorToasts().map((toast) => toast.title)).toStrictEqual([
        'clientHandler.templateBlockedTitle',
      ])
      expect(downloadToasts()).toHaveLength(0)
      expect(testApp.store.getters['job/getAll']).toHaveLength(0)
      expect(downloadLink(wrapper).classes()).not.toContain(
        'context__menu-item-link--loading'
      )
    })

    test('sends an anonymous visitor to the login page and back', async () => {
      const wrapper = await mountWithMenu({ template: userTemplate })

      await clickDownload(wrapper)

      expect(push).toHaveBeenCalledWith({
        name: 'login',
        query: { original: '/template/crm-a1b2c3' },
      })
      expect(downloadRequests()).toHaveLength(0)
    })
  })

  describe('without a workspace', () => {
    const userTemplate = {
      id: 5,
      type: 'user',
      slug: 'crm-a1b2c3',
      name: 'CRM',
    }

    const signInWithoutWorkspace = () =>
      testApp.authenticate({
        id: 1,
        preferences: {},
        completed_onboarding: true,
      })

    const mountWithoutWorkspace = (props, canCreateWorkspace = true) =>
      testApp.mount(TemplateInstall, {
        props,
        global: {
          mocks: { $hasPermission: () => canCreateWorkspace },
        },
      })

    describe.each([
      ['an official template', template],
      ['a user template', userTemplate],
    ])('of %s', (_name, shownTemplate) => {
      test('creates a workspace and installs into it without leaving', async () => {
        signInWithoutWorkspace()
        const wrapper = await mountWithoutWorkspace({ template: shownTemplate })

        expect(wrapper.find('.template-install__no-workspace').text()).toBe(
          'templateInstall.noWorkspace'
        )
        expect(wrapper.find('.template-install__workspace').exists()).toBe(
          false
        )
        expect(wrapper.find('.template-install__use').exists()).toBe(false)

        await wrapper
          .find('.template-install__create-workspace')
          .trigger('click')
        const modal = wrapper.findComponent(CreateWorkspaceModal)
        expect(modal.vm.$refs.modal.isOpen()).toBe(true)

        // Done by the modal before it reports the new workspace.
        await testApp.store.dispatch('workspace/forceCreate', {
          id: 3,
          name: 'New',
        })
        modal.vm.$emit('created', testApp.store.getters['workspace/get'](3))
        await flushPromises()

        expect(wrapper.find('.template-install__no-workspace').exists()).toBe(
          false
        )
        expect(
          wrapper.find('.template-install__create-workspace').exists()
        ).toBe(false)
        expect(
          wrapper.findComponent({ name: 'Dropdown' }).props('modelValue')
        ).toBe(3)
        expect(
          wrapper.find('.template-install__use').attributes('disabled')
        ).toBeUndefined()

        testApp.mock
          .onPost(`/templates/install/3/${shownTemplate.id}/async/`)
          .reply(202, { id: 10, type: 'install_template', state: 'finished' })
        await clickUse(wrapper)

        expect(testApp.mock.history.post.map((r) => r.url)).toStrictEqual([
          `/templates/install/3/${shownTemplate.id}/async/`,
        ])
        expect(wrapper.emitted('installed')).toHaveLength(1)
        expect(push).not.toHaveBeenCalled()
      })

      test('asks to be invited when the user may not create a workspace', async () => {
        signInWithoutWorkspace()
        const wrapper = await mountWithoutWorkspace(
          { template: shownTemplate },
          false
        )

        expect(wrapper.find('.template-install__no-workspace').text()).toBe(
          'templateInstall.noWorkspaceAskInvite'
        )
        expect(
          wrapper.find('.template-install__create-workspace').exists()
        ).toBe(false)
        expect(wrapper.find('.template-install__workspace').exists()).toBe(
          false
        )
        expect(
          wrapper.find('.template-install__use').attributes('disabled')
        ).toBeDefined()
      })
    })

    test('shows neither to an anonymous visitor', async () => {
      const wrapper = await mountWithoutWorkspace({ template })

      expect(wrapper.find('.template-install__no-workspace').exists()).toBe(
        false
      )
      expect(wrapper.find('.template-install__create-workspace').exists()).toBe(
        false
      )
      expect(wrapper.findComponent(CreateWorkspaceModal).exists()).toBe(false)
    })
  })
})
