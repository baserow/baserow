import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
import { permission } from '@baserow/test/helpers/permission'
import { heldBack } from '@baserow/test/helpers/heldBack'
import { seedWorkspaces, updateJob } from '@baserow/test/helpers/store'
import UpdateUserTemplateModal from '@baserow/modules/core/components/template/UpdateUserTemplateModal'

vi.mock('#app', async (importOriginal) =>
  (await import('@baserow/test/helpers/permission')).mockHasPermission(
    importOriginal
  )
)

const categories = [
  { id: 1, name: 'Business' },
  { id: 2, name: 'Personal' },
]

const userTemplate = (values = {}) => ({
  id: 3,
  type: 'user',
  name: 'Sprint Tracker',
  description: 'Plan sprints',
  icon: 'iconoir-agile',
  workspace_id: 103,
  categories: [{ id: 2, name: 'Personal' }],
  state: 'private',
  reason: null,
  source_workspace_id: 1,
  source_application_ids: [11],
  ...values,
})

const runningJob = (values = {}) => ({
  id: 7,
  type: 'create_user_template',
  state: 'pending',
  progress_percentage: 0,
  human_readable_error: '',
  workspace_id: null,
  application_ids: [],
  name: 'Sprints',
  description: 'Plan sprints',
  icon: 'iconoir-agile',
  category_ids: [2],
  template: 3,
  revision: null,
  ...values,
})

describe('UpdateUserTemplateModal', () => {
  let testApp = null
  let refreshed = 0

  beforeEach(async () => {
    testApp = new TestApp()
    permission.check = () => true
    refreshed = 0
    const { store } = testApp
    const dispatch = store.dispatch
    vi.spyOn(store, 'dispatch').mockImplementation((type, ...args) => {
      if (type === 'auth/refresh') {
        refreshed += 1
        return Promise.resolve()
      }
      return dispatch.call(store, type, ...args)
    })
    const database = { type: 'database', tables: [] }
    await seedWorkspaces(
      store,
      [
        { id: 1, name: 'Acme' },
        { id: 2, name: 'Side project' },
      ],
      [
        { id: 11, name: 'CRM', workspace: { id: 1 }, ...database },
        { id: 12, name: 'Tasks', workspace: { id: 1 }, ...database },
        { id: 21, name: 'Notes', workspace: { id: 2 }, ...database },
      ]
    )
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.store.dispatch('job/clearAll')
    await testApp.afterEach()
  })

  const mountAndShow = async (mode, template = userTemplate()) => {
    const wrapper = await testApp.mount(UpdateUserTemplateModal, {
      props: { template, mode, categories },
      global: { stubs: { Modal: ModalStub } },
    })
    await wrapper.vm.show()
    await flushPromises()
    return wrapper
  }

  const button = (wrapper, label) =>
    wrapper.findAll('button').find((button) => button.text() === label)

  const saveButton = (wrapper) =>
    button(wrapper, 'updateUserTemplateModal.save')

  const updateButton = (wrapper) =>
    button(wrapper, 'updateUserTemplateModal.update')

  const title = (wrapper) => wrapper.find('.user-template-modal__title').text()

  const selectedWorkspaceId = (wrapper) =>
    wrapper.findComponent({ name: 'Dropdown' }).props('modelValue')

  const selectedApplicationIds = (wrapper) =>
    wrapper
      .findComponent({ name: 'ApplicationSelector' })
      .props('selectedApplicationIds')

  const isModalOpen = (wrapper) =>
    wrapper.findComponent({ name: 'Modal' }).vm.open

  describe('details', () => {
    test('are prefilled from the template', async () => {
      const wrapper = await mountAndShow('details')

      expect(title(wrapper)).toBe('updateUserTemplateModal.detailsTitle')
      expect(wrapper.find('input').element.value).toBe('Sprint Tracker')
      expect(wrapper.find('textarea').element.value).toBe('Plan sprints')
      expect(
        wrapper.find('.user-template-form__icon-button i').classes()
      ).toContain('iconoir-agile')
      expect(
        wrapper.findAll('.chips').map((chip) => chip.classes('chips--active'))
      ).toStrictEqual([false, true])
    })

    test('can only be saved when changed', async () => {
      const wrapper = await mountAndShow('details')

      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

      await wrapper.find('input').setValue('Sprints')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()

      await wrapper.find('input').setValue('Sprint Tracker ')
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

      await wrapper.find('textarea').setValue('Plan sprints ')
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

      await wrapper.findAll('.chips')[0].trigger('click')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    test('ignore the order the categories are picked in', async () => {
      const wrapper = await mountAndShow(
        'details',
        userTemplate({ categories: [...categories] })
      )

      await wrapper.findAll('.chips')[0].trigger('click')
      await wrapper.findAll('.chips')[0].trigger('click')

      expect(wrapper.vm.values.categoryIds).toStrictEqual([2, 1])
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    })

    test('keep a category that cannot be picked anymore', async () => {
      const wrapper = await mountAndShow(
        'details',
        userTemplate({ categories: [{ id: 5, name: 'Retired' }] })
      )

      expect(
        wrapper
          .findAll('.chips')
          .map((chip) => [chip.text(), chip.classes('chips--active')])
      ).toStrictEqual([
        ['Business', false],
        ['Personal', false],
        ['Retired', true],
      ])
    })

    test('send the template and the details', async () => {
      let request = null
      testApp.mock.onPost('/jobs/').reply((config) => {
        request = JSON.parse(config.data)
        return [200, runningJob()]
      })
      const wrapper = await mountAndShow('details')

      await wrapper.find('input').setValue(' Sprints ')
      await wrapper.find('textarea').setValue(' Plan sprints\n')
      await saveButton(wrapper).trigger('click')
      await flushPromises()

      expect(request).toStrictEqual({
        type: 'create_user_template',
        template_id: 3,
        name: 'Sprints',
        description: 'Plan sprints',
        icon: 'iconoir-agile',
        category_ids: [2],
      })
      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
      expect(wrapper.find('input').attributes('disabled')).toBeDefined()
    })

    test('need a name and a category', async () => {
      testApp.mock.onPost('/jobs/').reply(200, runningJob())
      const wrapper = await mountAndShow('details')

      await wrapper.find('input').setValue('  ')
      await wrapper.findAll('.chips')[1].trigger('click')
      await saveButton(wrapper).trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('userTemplateDetailsForm.nameRequired')
      expect(wrapper.text()).toContain(
        'userTemplateDetailsForm.categoriesRequired'
      )
      expect(testApp.mock.history.post).toHaveLength(0)
    })

    test("don't point to the details when a category is refused", async () => {
      testApp.mock.onPost('/jobs/').reply(400, {
        error: 'ERROR_INVALID_TEMPLATE_CATEGORY',
        detail: 'A category is refused.',
      })
      const wrapper = await mountAndShow('details')

      await wrapper.find('input').setValue('Sprints')
      await saveButton(wrapper).trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('A category is refused.')
      expect(wrapper.text()).not.toContain(
        'updateUserTemplateModal.invalidKeptDetails'
      )
    })
  })

  describe('content', () => {
    test('preselects the source workspace and applications', async () => {
      const wrapper = await mountAndShow('content')

      expect(title(wrapper)).toBe('updateUserTemplateModal.contentTitle')
      expect(selectedWorkspaceId(wrapper)).toBe(1)
      expect(selectedApplicationIds(wrapper)).toStrictEqual([11])
      expect(updateButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    test('preselects only the source applications that still exist', async () => {
      const wrapper = await mountAndShow(
        'content',
        userTemplate({ source_application_ids: [12, 99] })
      )

      expect(selectedApplicationIds(wrapper)).toStrictEqual([12])
    })

    test('starts with the selected workspace without the source one', async () => {
      const wrapper = await mountAndShow(
        'content',
        userTemplate({ source_workspace_id: 9, source_application_ids: [91] })
      )

      expect(selectedWorkspaceId(wrapper)).toBe(1)
      expect(selectedApplicationIds(wrapper)).toStrictEqual([11, 12])
    })

    test("doesn't preselect a workspace that can't be exported", async () => {
      permission.check = (operation, context, workspaceId) => workspaceId !== 1
      const wrapper = await mountAndShow('content')

      expect(selectedWorkspaceId(wrapper)).toBe(2)
      expect(selectedApplicationIds(wrapper)).toStrictEqual([21])
    })

    test('needs at least one application', async () => {
      const wrapper = await mountAndShow('content')

      wrapper
        .findComponent({ name: 'ApplicationSelector' })
        .vm.$emit('update', [])
      await flushPromises()

      expect(updateButton(wrapper).attributes('disabled')).toBeDefined()
    })

    test('sends the template and the content, and can be cancelled', async () => {
      let request = null
      testApp.mock.onPost('/jobs/').reply((config) => {
        request = JSON.parse(config.data)
        return [200, runningJob({ workspace_id: 1, application_ids: [11] })]
      })
      testApp.mock
        .onPost('/jobs/7/cancel/')
        .reply(200, runningJob({ state: 'cancelled' }))
      const wrapper = await mountAndShow('content')

      await updateButton(wrapper).trigger('click')
      await flushPromises()

      expect(request).toStrictEqual({
        type: 'create_user_template',
        template_id: 3,
        workspace_id: 1,
        application_ids: [11],
      })
      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
      expect(
        wrapper.findComponent({ name: 'Dropdown' }).props('disabled')
      ).toBe(true)

      await wrapper.find('.modal-progress__cancel-button').trigger('click')
      await flushPromises()

      expect(testApp.mock.history.post.map((r) => r.url)).toContain(
        '/jobs/7/cancel/'
      )
      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(
        false
      )
      expect(selectedApplicationIds(wrapper)).toStrictEqual([11])
      expect(updateButton(wrapper).attributes('disabled')).toBeUndefined()
      expect(wrapper.emitted('updated')).toBeUndefined()
    })

    test.each([
      'ERROR_INVALID_TEMPLATE_CATEGORY',
      'ERROR_INVALID_TEMPLATE_ICON',
    ])(
      'points to the details when the kept ones are refused with %s',
      async (error) => {
        testApp.mock
          .onPost('/jobs/')
          .reply(400, { error, detail: 'The details are refused.' })
        const wrapper = await mountAndShow('content')

        await updateButton(wrapper).trigger('click')
        await flushPromises()

        expect(wrapper.text()).toContain(
          'updateUserTemplateModal.invalidKeptDetails'
        )
        expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(
          false
        )
      }
    )
  })

  describe('job', () => {
    const startContentUpdate = async () => {
      testApp.mock
        .onPost('/jobs/')
        .reply(200, runningJob({ workspace_id: 1, application_ids: [11] }))
      const wrapper = await mountAndShow('content')
      await updateButton(wrapper).trigger('click')
      await flushPromises()
      return wrapper
    }

    test('closes and refreshes when the template is updated', async () => {
      const wrapper = await startContentUpdate()

      await updateJob(testApp.store, 7, {
        state: 'finished',
        progress_percentage: 100,
      })

      expect(isModalOpen(wrapper)).toBe(false)
      expect(testApp.store.state.toast.items[0]).toMatchObject({
        type: 'success',
        title: 'updateUserTemplateModal.updated',
      })
      expect(refreshed).toBe(1)
      expect(wrapper.emitted('updated')).toHaveLength(1)
      expect(wrapper.emitted('updated')[0][0].template).toBe(3)
    })

    test('is handled as updated when it failed after the revision', async () => {
      const wrapper = await startContentUpdate()

      await updateJob(testApp.store, 7, {
        state: 'failed',
        human_readable_error: 'Failed',
        revision: 8,
      })

      expect(isModalOpen(wrapper)).toBe(false)
      expect(wrapper.emitted('updated')).toHaveLength(1)
      expect(testApp.store.state.toast.items[0]).toMatchObject({
        type: 'warning',
        title: 'updateUserTemplateModal.failedAfterUpdated',
      })
      expect(refreshed).toBe(1)
    })

    test('shows why the job failed', async () => {
      const wrapper = await startContentUpdate()

      await updateJob(testApp.store, 7, {
        state: 'failed',
        human_readable_error: 'Denied',
      })

      expect(isModalOpen(wrapper)).toBe(true)
      expect(wrapper.text()).toContain('Denied')
      // Already shown in the modal.
      expect(testApp.store.state.toast.items).toHaveLength(0)
      expect(wrapper.emitted('updated')).toBeUndefined()
      expect(refreshed).toBe(0)
      expect(updateButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    test('notifies why the job failed while closed', async () => {
      const wrapper = await startContentUpdate()
      wrapper.vm.hide()

      await updateJob(testApp.store, 7, {
        state: 'failed',
        human_readable_error: 'Denied',
      })

      expect(testApp.store.state.toast.items).toHaveLength(1)
      expect(testApp.store.state.toast.items[0]).toMatchObject({
        type: 'error',
        title: 'clientHandler.notCompletedTitle',
        message: 'Denied',
      })
      expect(wrapper.emitted('updated')).toBeUndefined()
    })

    test('shows a job that failed while closed once, with its inputs', async () => {
      testApp.mock.onPost('/jobs/').reply(200, runningJob())
      const wrapper = await mountAndShow('details')
      await wrapper.find('input').setValue('Sprints')
      await saveButton(wrapper).trigger('click')
      await flushPromises()
      wrapper.vm.hide()

      await updateJob(testApp.store, 7, {
        state: 'failed',
        human_readable_error: 'Denied',
      })
      await wrapper.vm.show()
      await flushPromises()

      expect(wrapper.text()).toContain('Denied')
      expect(wrapper.find('input').element.value).toBe('Sprints')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()

      wrapper.vm.hide()
      await wrapper.vm.show()
      await flushPromises()

      expect(wrapper.text()).not.toContain('Denied')
      expect(wrapper.find('input').element.value).toBe('Sprint Tracker')
    })

    test('notifies once when more than one modal follows the job', async () => {
      await testApp.store.dispatch(
        'job/forceCreate',
        runningJob({ workspace_id: 1, application_ids: [11] })
      )
      const wrappers = [
        await mountAndShow('content'),
        await mountAndShow('content'),
      ]

      await updateJob(testApp.store, 7, {
        state: 'finished',
        progress_percentage: 100,
      })

      expect(testApp.store.state.toast.items).toHaveLength(1)
      expect(refreshed).toBe(1)
      for (const wrapper of wrappers) {
        expect(isModalOpen(wrapper)).toBe(false)
        expect(wrapper.emitted('updated')).toHaveLength(1)
      }
    })

    test('explains a refused cancel', async () => {
      testApp.mock.onPost('/jobs/7/cancel/').reply(400, {
        error: 'ERROR_JOB_NOT_CANCELLABLE',
        detail: 'The job cannot be cancelled.',
      })
      const wrapper = await startContentUpdate()

      await wrapper.find('.modal-progress__cancel-button').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain(
        'updateUserTemplateModal.cannotBeCancelled'
      )
      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
    })

    test('shows a running update of the same template again', async () => {
      await testApp.store.dispatch(
        'job/forceCreate',
        runningJob({ workspace_id: 2, application_ids: [21] })
      )
      // Asked for the details, but the running job updates the content.
      const wrapper = await mountAndShow('details')

      expect(title(wrapper)).toBe('updateUserTemplateModal.contentTitle')
      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
      expect(selectedWorkspaceId(wrapper)).toBe(2)
      expect(selectedApplicationIds(wrapper)).toStrictEqual([21])
      expect(wrapper.find('.modal-progress__cancel-button').exists()).toBe(true)
    })

    test('keeps an update that is still being sent when shown again', async () => {
      const jobRequest = heldBack()
      testApp.mock.onPost('/jobs/').reply(jobRequest.reply)
      const wrapper = await mountAndShow('details')
      await wrapper.find('input').setValue('Sprints')
      await saveButton(wrapper).trigger('click')
      await flushPromises()

      expect(wrapper.find('input').attributes('disabled')).toBeDefined()

      wrapper.vm.hide()
      await wrapper.vm.show()
      await flushPromises()

      expect(wrapper.find('input').element.value).toBe('Sprints')
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

      jobRequest.send([200, runningJob()])
      await flushPromises()

      expect(wrapper.find('input').element.value).toBe('Sprints')
      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
    })

    test('shows a running details update again', async () => {
      await testApp.store.dispatch('job/forceCreate', runningJob())
      const wrapper = await mountAndShow('content')

      expect(title(wrapper)).toBe('updateUserTemplateModal.detailsTitle')
      expect(wrapper.find('input').element.value).toBe('Sprints')
      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
    })

    test("doesn't show the job of another template", async () => {
      await testApp.store.dispatch(
        'job/forceCreate',
        runningJob({ template: 4 })
      )
      const wrapper = await mountAndShow('details')

      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(
        false
      )
      expect(wrapper.find('input').element.value).toBe('Sprint Tracker')
    })

    test("doesn't show the job of a new template", async () => {
      await testApp.store.dispatch(
        'job/forceCreate',
        runningJob({ template: null, workspace_id: 1, application_ids: [11] })
      )
      const wrapper = await mountAndShow('details')

      expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(
        false
      )
    })
  })
})
