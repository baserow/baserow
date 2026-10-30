import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
import { permission } from '@baserow/test/helpers/permission'
import { heldBack } from '@baserow/test/helpers/heldBack'
import { seedWorkspaces, updateJob } from '@baserow/test/helpers/store'
import CreateUserTemplateModal from '@baserow/modules/core/components/template/CreateUserTemplateModal'
import UserTemplateContentForm from '@baserow/modules/core/components/template/UserTemplateContentForm'

vi.mock('#app', async (importOriginal) =>
  (await import('@baserow/test/helpers/permission')).mockHasPermission(
    importOriginal
  )
)

const categories = [
  { id: 1, name: 'Business' },
  { id: 2, name: 'Personal' },
]

const runningJob = (values = {}) => ({
  id: 7,
  type: 'create_user_template',
  state: 'pending',
  progress_percentage: 0,
  human_readable_error: '',
  workspace_id: 1,
  application_ids: [11],
  name: 'Sprint Tracker',
  description: 'Plan sprints',
  icon: 'iconoir-agile',
  category_ids: [2],
  make_public: false,
  template: null,
  ...values,
})

describe('CreateUserTemplateModal', () => {
  let testApp = null

  beforeEach(async () => {
    testApp = new TestApp()
    permission.check = () => true
    const database = { type: 'database', tables: [] }
    await seedWorkspaces(
      testApp.store,
      [
        { id: 1, name: 'Acme' },
        { id: 2, name: 'Side project' },
        { id: 3, name: 'Read only' },
      ],
      [
        { id: 11, name: 'CRM', workspace: { id: 1 }, ...database },
        {
          id: 12,
          name: 'Site',
          workspace: { id: 1 },
          type: 'builder',
          pages: [],
        },
        { id: 21, name: 'Notes', workspace: { id: 2 }, ...database },
        { id: 31, name: 'Shared', workspace: { id: 3 }, ...database },
      ]
    )
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.store.dispatch('job/clearAll')
    await testApp.afterEach()
  })

  const mountAndShow = async (props = { categories }) => {
    const wrapper = await testApp.mount(CreateUserTemplateModal, {
      props,
      global: { stubs: { Modal: ModalStub } },
    })
    await wrapper.vm.show()
    await flushPromises()
    return wrapper
  }

  const fillDetails = async (wrapper) => {
    await wrapper.find('input').setValue('Sprint Tracker')
    await wrapper.find('textarea').setValue('Plan sprints')
    await wrapper.findAll('.chips')[1].trigger('click')
  }

  const continueButton = (wrapper) =>
    wrapper
      .findAll('button')
      .find((button) => button.text() === 'createUserTemplateModal.continue')

  const createButton = (wrapper) =>
    wrapper
      .findAll('button')
      .find((button) => button.text() === 'createUserTemplateModal.create')

  const goToContent = async (wrapper) => {
    await fillDetails(wrapper)
    await continueButton(wrapper).trigger('click')
    await flushPromises()
  }

  const selectedApplicationIds = (wrapper) =>
    wrapper
      .findComponent({ name: 'ApplicationSelector' })
      .props('selectedApplicationIds')

  const selectWorkspace = async (wrapper, workspaceId) => {
    wrapper
      .findComponent({ name: 'Dropdown' })
      .vm.$emit('update:modelValue', workspaceId)
    await flushPromises()
  }

  test('keeps the inputs when switching steps', async () => {
    const wrapper = await mountAndShow()
    await goToContent(wrapper)

    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'createUserTemplateModal.contentTitle'
    )

    await wrapper.find('.user-template-modal__back').trigger('click')

    expect(wrapper.find('input').element.value).toBe('Sprint Tracker')
    expect(wrapper.find('textarea').element.value).toBe('Plan sprints')
    expect(
      wrapper.findAll('.chips').map((chip) => chip.classes('chips--active'))
    ).toStrictEqual([false, true])
  })

  test('needs a name and a category to continue', async () => {
    const wrapper = await mountAndShow()

    await continueButton(wrapper).trigger('click')

    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'createUserTemplateModal.detailsTitle'
    )
    expect(wrapper.text()).toContain('userTemplateDetailsForm.nameRequired')
    expect(wrapper.text()).toContain(
      'userTemplateDetailsForm.categoriesRequired'
    )
  })

  test('counts and limits the description', async () => {
    const wrapper = await mountAndShow()

    expect(wrapper.find('textarea').attributes('maxlength')).toBe('80')
    expect(wrapper.text()).toContain('0 / 80')

    await wrapper.find('textarea').setValue('Plan sprints')

    expect(wrapper.text()).toContain('12 / 80')
  })

  test('picks an icon', async () => {
    const wrapper = await mountAndShow()

    expect(
      wrapper.find('.user-template-form__icon-button i').classes()
    ).toContain('iconoir-view-grid')

    wrapper
      .findComponent({ name: 'TemplateIconSelectContext' })
      .vm.$emit('selected', 'iconoir-agile')
    await flushPromises()

    expect(
      wrapper.find('.user-template-form__icon-button i').classes()
    ).toContain('iconoir-agile')
  })

  test('preselects all applications and needs at least one', async () => {
    const wrapper = await mountAndShow()
    await goToContent(wrapper)

    expect(selectedApplicationIds(wrapper)).toStrictEqual([11, 12])
    expect(createButton(wrapper).attributes('disabled')).toBeUndefined()

    wrapper
      .findComponent({ name: 'ApplicationSelector' })
      .vm.$emit('update', [])
    await flushPromises()

    expect(createButton(wrapper).attributes('disabled')).toBeDefined()
  })

  test('starts the application selection again for another workspace', async () => {
    const wrapper = await mountAndShow()
    await goToContent(wrapper)
    wrapper
      .findComponent({ name: 'ApplicationSelector' })
      .vm.$emit('update', [12])

    await selectWorkspace(wrapper, 2)

    expect(selectedApplicationIds(wrapper)).toStrictEqual([21])

    await wrapper.find('.user-template-modal__back').trigger('click')

    expect(wrapper.find('input').element.value).toBe('Sprint Tracker')
    expect(wrapper.find('textarea').element.value).toBe('Plan sprints')
  })

  test('disables the workspaces the user cannot export', async () => {
    permission.check = (operation, context, workspaceId) =>
      operation === 'workspace.export' && workspaceId !== 3
    const wrapper = await mountAndShow()
    await goToContent(wrapper)

    expect(
      wrapper
        .findAllComponents({ name: 'DropdownItem' })
        .map((item) => [item.props('value'), item.props('disabled')])
    ).toStrictEqual([
      [1, false],
      [2, false],
      [3, true],
    ])
  })

  test('explains why a workspace is disabled', async () => {
    permission.check = (operation, context, workspaceId) => workspaceId !== 3
    testApp.store.commit('application/DELETE_ITEM', 21)
    const wrapper = await mountAndShow()
    await goToContent(wrapper)

    expect(
      wrapper
        .findAllComponents({ name: 'DropdownItem' })
        .map((item) => [
          item.props('value'),
          item.props('disabled'),
          item.props('description'),
        ])
    ).toStrictEqual([
      [1, false, null],
      [2, true, 'userTemplateContentForm.workspaceEmpty'],
      [3, true, 'userTemplateContentForm.workspaceNoPermission'],
    ])
  })

  test('only fetches the permissions that are not loaded yet', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 4,
      name: 'Other',
    })
    testApp.mock.onGet('/workspaces/4/permissions/').reply(200, [])
    const wrapper = await mountAndShow()

    expect(
      testApp.mock.history.get
        .map((request) => request.url)
        .filter((url) => url.includes('/permissions/'))
    ).toStrictEqual(['/workspaces/4/permissions/'])
    expect(testApp.store.getters['workspace/get'](4)._.permissionsLoaded).toBe(
      true
    )

    // Loaded once.
    wrapper.vm.hide()
    await wrapper.vm.show()
    await flushPromises()
    expect(
      testApp.mock.history.get.filter((r) => r.url.includes('/permissions/'))
    ).toHaveLength(1)
  })

  test("doesn't ask for a category when there are none", async () => {
    let request = null
    testApp.mock.onPost('/jobs/').reply((config) => {
      request = JSON.parse(config.data)
      return [200, runningJob({ category_ids: [] })]
    })
    const wrapper = await mountAndShow({ categories: [] })

    expect(wrapper.find('.chips').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('userTemplateDetailsForm.categories')

    await wrapper.find('input').setValue('Sprint Tracker')
    await continueButton(wrapper).trigger('click')
    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'createUserTemplateModal.contentTitle'
    )

    await createButton(wrapper).trigger('click')
    await flushPromises()
    expect(request.category_ids).toStrictEqual([])
  })

  test('starts with an exportable workspace', async () => {
    permission.check = (operation, context, workspaceId) => workspaceId === 2
    const wrapper = await mountAndShow()
    await goToContent(wrapper)

    expect(
      wrapper.findComponent({ name: 'Dropdown' }).props('modelValue')
    ).toBe(2)
    expect(selectedApplicationIds(wrapper)).toStrictEqual([21])
  })

  test("doesn't switch a workspace the author picked", async () => {
    let deniedWorkspaceId = null
    permission.check = (operation, context, workspaceId) =>
      workspaceId !== deniedWorkspaceId
    const wrapper = await mountAndShow()
    await goToContent(wrapper)
    await selectWorkspace(wrapper, 2)

    // The permissions of the workspace load after it was picked.
    deniedWorkspaceId = 2
    await wrapper.findComponent(UserTemplateContentForm).vm.loadPermissions()
    await flushPromises()

    expect(
      wrapper.findComponent({ name: 'Dropdown' }).props('modelValue')
    ).toBe(2)
    expect(selectedApplicationIds(wrapper)).toStrictEqual([21])
  })

  test('keeps the picked workspace and its permissions between the steps', async () => {
    let deniedWorkspaceId = null
    permission.check = (operation, context, workspaceId) =>
      workspaceId !== deniedWorkspaceId
    const dispatch = vi.spyOn(testApp.store, 'dispatch')
    const wrapper = await mountAndShow()
    await goToContent(wrapper)
    await selectWorkspace(wrapper, 2)
    const fetched = dispatch.mock.calls.filter(
      ([type]) => type === 'workspace/fetchPermissions'
    ).length

    await wrapper.find('.user-template-modal__back').trigger('click')
    deniedWorkspaceId = 2
    await continueButton(wrapper).trigger('click')
    await flushPromises()

    expect(
      dispatch.mock.calls.filter(
        ([type]) => type === 'workspace/fetchPermissions'
      )
    ).toHaveLength(fetched)
    expect(
      wrapper.findComponent({ name: 'Dropdown' }).props('modelValue')
    ).toBe(2)
    expect(selectedApplicationIds(wrapper)).toStrictEqual([21])
  })

  test('sends the request and shows the progress', async () => {
    let request = null
    testApp.mock.onPost('/jobs/').reply((config) => {
      request = JSON.parse(config.data)
      return [200, runningJob()]
    })
    testApp.mock
      .onPost('/jobs/7/cancel/')
      .reply(200, runningJob({ state: 'cancelled' }))
    const wrapper = await mountAndShow()
    await goToContent(wrapper)
    wrapper
      .findComponent({ name: 'ApplicationSelector' })
      .vm.$emit('update', [11])
    await flushPromises()

    await createButton(wrapper).trigger('click')
    await flushPromises()

    expect(request).toStrictEqual({
      type: 'create_user_template',
      workspace_id: 1,
      application_ids: [11],
      name: 'Sprint Tracker',
      description: 'Plan sprints',
      icon: 'iconoir-view-grid',
      category_ids: [2],
      make_public: false,
      public_listing_consent: false,
    })
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'Dropdown' }).props('disabled')).toBe(
      true
    )

    await wrapper.find('.modal-progress__cancel-button').trigger('click')
    await flushPromises()

    expect(testApp.mock.history.post.map((r) => r.url)).toContain(
      '/jobs/7/cancel/'
    )
    // Cancelled: back to the content step with the inputs kept.
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(false)
    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'createUserTemplateModal.contentTitle'
    )
    expect(selectedApplicationIds(wrapper)).toStrictEqual([11])
    expect(createButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  const chooseVisibility = async (wrapper, label) => {
    await wrapper
      .findAll('.segment-control__button')
      .find((b) => b.text() === label)
      .trigger('click')
    await flushPromises()
  }

  const agreeToPublicListing = async (wrapper) => {
    await wrapper
      .find('.user-template-form__consent input[type="checkbox"]')
      .setValue(true)
    await flushPromises()
  }

  test.each([
    [false, 'publicDescription'],
    [true, 'publicReviewDescription'],
  ])(
    'makes the template public only once the author agreed (approval: %s)',
    async (requireApproval, description) => {
      testApp.store.commit('settings/UPDATE_SETTINGS', {
        user_templates_require_approval: requireApproval,
      })
      let request = null
      testApp.mock.onPost('/jobs/').reply((config) => {
        request = JSON.parse(config.data)
        return [200, runningJob({ make_public: true })]
      })
      const wrapper = await mountAndShow()
      await fillDetails(wrapper)

      await chooseVisibility(wrapper, 'userTemplateVisibilityForm.public')
      expect(wrapper.text()).toContain(
        `userTemplateVisibilityForm.${description}`
      )
      expect(continueButton(wrapper).attributes('disabled')).toBeDefined()

      await agreeToPublicListing(wrapper)
      await continueButton(wrapper).trigger('click')
      await flushPromises()
      await createButton(wrapper).trigger('click')
      await flushPromises()

      expect(request).toMatchObject({
        make_public: true,
        public_listing_consent: true,
      })
    }
  )

  test('stays private when Private is chosen after agreeing to Public', async () => {
    let request = null
    testApp.mock.onPost('/jobs/').reply((config) => {
      request = JSON.parse(config.data)
      return [200, runningJob()]
    })
    const wrapper = await mountAndShow()
    await fillDetails(wrapper)

    await chooseVisibility(wrapper, 'userTemplateVisibilityForm.public')
    await agreeToPublicListing(wrapper)
    await chooseVisibility(wrapper, 'userTemplateVisibilityForm.private')
    expect(wrapper.find('.user-template-form__consent').exists()).toBe(false)

    await continueButton(wrapper).trigger('click')
    await flushPromises()
    await createButton(wrapper).trigger('click')
    await flushPromises()

    expect(request).toMatchObject({
      make_public: false,
      public_listing_consent: false,
    })
  })

  test('closes when the template is created', async () => {
    testApp.mock.onPost('/jobs/').reply(200, runningJob())
    const wrapper = await mountAndShow()
    await goToContent(wrapper)

    await createButton(wrapper).trigger('click')
    await flushPromises()
    await updateJob(testApp.store, 7, {
      state: 'finished',
      progress_percentage: 100,
      template: 3,
    })

    expect(wrapper.emitted('created')).toHaveLength(1)
    expect(wrapper.emitted('created')[0][0].template).toBe(3)
    expect(wrapper.findComponent({ name: 'Modal' }).vm.open).toBe(false)

    // Shown again with an empty form.
    await wrapper.vm.show()
    await flushPromises()
    expect(wrapper.find('input').element.value).toBe('')
  })

  test('shows why the job failed', async () => {
    testApp.mock.onPost('/jobs/').reply(200, runningJob())
    const wrapper = await mountAndShow()
    await goToContent(wrapper)

    await createButton(wrapper).trigger('click')
    await flushPromises()
    await updateJob(testApp.store, 7, {
      state: 'failed',
      human_readable_error: 'Permission denied',
    })

    expect(wrapper.text()).toContain('Permission denied')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(createButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  test.each([
    [false, 'createUserTemplateModal.failedAfterCreated'],
    [true, 'createUserTemplateModal.failedPublicAfterCreated'],
  ])(
    'is handled as created when it failed after the template was created (public %s)',
    async (makePublic, title) => {
      testApp.mock
        .onPost('/jobs/')
        .reply(200, runningJob({ make_public: makePublic }))
      const wrapper = await mountAndShow()
      await goToContent(wrapper)

      await createButton(wrapper).trigger('click')
      await flushPromises()
      await updateJob(testApp.store, 7, {
        state: 'failed',
        human_readable_error: 'Failed',
        template: 3,
        revision: 3,
      })

      expect(wrapper.emitted('created')).toHaveLength(1)
      expect(wrapper.findComponent({ name: 'Modal' }).vm.open).toBe(false)
      expect(testApp.store.state.toast.items[0]).toMatchObject({
        type: 'warning',
        title,
      })
    }
  )

  test('explains a refused cancel', async () => {
    testApp.mock.onPost('/jobs/').reply(200, runningJob({ state: 'started' }))
    testApp.mock.onPost('/jobs/7/cancel/').reply(400, {
      error: 'ERROR_JOB_NOT_CANCELLABLE',
      detail: 'The job cannot be cancelled.',
    })
    const wrapper = await mountAndShow()
    await goToContent(wrapper)
    await createButton(wrapper).trigger('click')
    await flushPromises()

    await wrapper.find('.modal-progress__cancel-button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(
      'createUserTemplateModal.cannotBeCancelled'
    )
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
  })

  test('shows a job that failed while it was closed once', async () => {
    testApp.mock.onPost('/jobs/').reply(200, runningJob())
    const wrapper = await mountAndShow()
    await goToContent(wrapper)
    await createButton(wrapper).trigger('click')
    await flushPromises()
    wrapper.vm.hide()

    await updateJob(testApp.store, 7, {
      state: 'failed',
      human_readable_error: 'Permission denied',
    })
    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.text()).toContain('Permission denied')
    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'createUserTemplateModal.contentTitle'
    )
    expect(selectedApplicationIds(wrapper)).toStrictEqual([11, 12])
    expect(createButton(wrapper).attributes('disabled')).toBeUndefined()

    wrapper.vm.hide()
    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.text()).not.toContain('Permission denied')
    expect(wrapper.find('input').element.value).toBe('')
  })

  test('shows a job started from another wizard instead of a failed one', async () => {
    testApp.mock.onPost('/jobs/').reply(200, runningJob())
    const wrapper = await mountAndShow()
    await goToContent(wrapper)
    await createButton(wrapper).trigger('click')
    await flushPromises()
    await updateJob(testApp.store, 7, {
      state: 'failed',
      human_readable_error: 'Permission denied',
    })
    wrapper.vm.hide()

    await testApp.store.dispatch(
      'job/forceCreate',
      runningJob({
        id: 8,
        name: 'Roadmap',
        workspace_id: 2,
        application_ids: [21],
      })
    )
    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.text()).not.toContain('Permission denied')
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
    expect(wrapper.vm.job.id).toBe(8)
    expect(wrapper.vm.values).toMatchObject({
      name: 'Roadmap',
      workspaceId: 2,
      applicationIds: [21],
    })
  })

  test('keeps a template that is still being sent when shown again', async () => {
    const jobRequest = heldBack()
    testApp.mock.onPost('/jobs/').reply(jobRequest.reply)
    const wrapper = await mountAndShow()
    await goToContent(wrapper)
    await createButton(wrapper).trigger('click')
    await flushPromises()

    expect(
      wrapper.find('.user-template-modal__back').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.findComponent({ name: 'Dropdown' }).props('disabled')).toBe(
      true
    )

    wrapper.vm.hide()
    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'createUserTemplateModal.contentTitle'
    )
    expect(wrapper.vm.values.name).toBe('Sprint Tracker')
    expect(createButton(wrapper).attributes('disabled')).toBeDefined()

    jobRequest.send([200, runningJob()])
    await flushPromises()

    expect(wrapper.vm.values.name).toBe('Sprint Tracker')
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
  })

  test('shows a running job again', async () => {
    await testApp.store.dispatch(
      'job/forceCreate',
      runningJob({ make_public: true })
    )
    const wrapper = await mountAndShow()

    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'createUserTemplateModal.contentTitle'
    )
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
    expect(selectedApplicationIds(wrapper)).toStrictEqual([11])
    expect(wrapper.find('.modal-progress__cancel-button').exists()).toBe(true)

    // Closing it during the run keeps the job.
    wrapper.vm.hide()
    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
    expect(wrapper.vm.values).toStrictEqual({
      icon: 'iconoir-agile',
      name: 'Sprint Tracker',
      description: 'Plan sprints',
      categoryIds: [2],
      workspaceId: 1,
      applicationIds: [11],
      makePublic: true,
      publicListingConsent: true,
    })
  })

  test("doesn't show the job of a template update", async () => {
    await testApp.store.dispatch(
      'job/forceCreate',
      runningJob({ template: 3, application_ids: [] })
    )
    const wrapper = await mountAndShow()

    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'createUserTemplateModal.detailsTitle'
    )
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(false)
    expect(wrapper.find('input').element.value).toBe('')
  })
})
