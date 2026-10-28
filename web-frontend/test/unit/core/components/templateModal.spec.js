import { defineComponent } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplateModal from '@baserow/modules/core/components/template/TemplateModal'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'

const projectTracker = {
  id: 1,
  slug: 'project-tracker',
  name: 'Project Tracker',
}
const recipeBook = { id: 2, slug: 'recipe-book', name: 'Recipe Book' }

const categories = [
  { id: 1, name: 'Business', templates: [projectTracker] },
  { id: 2, name: 'Personal', templates: [recipeBook] },
]
// The id of an official template, to show that it doesn't pick its categories.
const sprintTracker = {
  id: 2,
  type: 'user',
  slug: 'sprint-tracker-a1b2c3',
  name: 'Sprint Tracker',
  workspace_id: 102,
  categories: [{ id: 7, name: 'Agile' }],
}

const ModalStub = defineComponent({
  name: 'Modal',
  props: ['keepContent', 'fullScreen', 'closeButton'],
  emits: ['show', 'hidden'],
  methods: {
    show() {
      this.$emit('show')
    },
    hide() {
      this.$emit('hidden')
    },
  },
  template: '<div><slot /></div>',
})

describe('TemplateModal', () => {
  const mountComponent = () => {
    return shallowMount(TemplateModal, {
      propsData: {
        workspace: {
          id: 1,
        },
      },
      global: {
        stubs: {
          Modal: ModalStub,
          TemplateList: true,
          TemplateDetails: true,
        },
        mocks: { $featureFlagIsEnabled: () => false },
      },
    })
  }

  it('keeps the root modal content mounted while closed', () => {
    const wrapper = mountComponent()

    expect(wrapper.findComponent({ name: 'Modal' }).props('keepContent')).toBe(
      ''
    )
  })
})

describe('TemplateModal navigation', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.mock.onGet('/templates/').reply(200, categories)
  })

  afterEach(async () => {
    mocks = {}
    refreshList = vi.fn()
    showCreateModal = vi.fn()
    showUpdateModal = vi.fn()
    showDeleteModal = vi.fn()
    removeFromList = vi.fn()
    await testApp.afterEach()
  })

  let mocks = {}

  const stubs = {
    Modal: ModalStub,
    TemplateDetails: defineComponent({
      name: 'TemplateDetails',
      props: ['template', 'categories', 'workspace', 'showBack', 'isOwn'],
      emits: ['back', 'installed', 'outdated', 'edit', 'delete'],
      template: `<div class="details">
        {{ template.name }}: {{ categories.map((c) => c.name).join(',') }}
        <a class="details__back" @click="$emit('back')" />
        <a class="details__edit" @click="$emit('edit', 'details')" />
        <a class="details__delete" @click="$emit('delete', template)" />
        <a class="details__outdated" @click="$emit('outdated')" />
      </div>`,
    }),
    TemplateList: defineComponent({
      name: 'TemplateList',
      props: ['categories', 'active'],
      emits: ['selected'],
      template: `<div class="list">
        <slot name="head" />
        <a class="list__recipe-book" @click="$emit('selected', categories[1].templates[0])" />
      </div>`,
    }),
    UserTemplateList: defineComponent({
      name: 'UserTemplateList',
      props: ['active'],
      emits: ['selected', 'create', 'edit', 'delete'],
      template: `<div class="own-list">
        <slot name="head" />
        <a class="own-list__sprint-tracker" @click="$emit('selected', sprintTracker)" />
        <a class="own-list__create" @click="$emit('create')" />
        <a class="own-list__edit" @click="$emit('edit', sprintTracker, 'content')" />
        <a class="own-list__delete" @click="$emit('delete', sprintTracker)" />
      </div>`,
      setup: () => ({ sprintTracker }),
      methods: {
        refresh() {
          refreshList()
        },
        remove(...args) {
          removeFromList(...args)
        },
      },
    }),
    CreateUserTemplateModal: defineComponent({
      name: 'CreateUserTemplateModal',
      props: ['categories'],
      emits: ['created', 'hidden'],
      methods: {
        show() {
          showCreateModal()
        },
      },
      template: '<div class="create-modal" />',
    }),
    UpdateUserTemplateModal: defineComponent({
      name: 'UpdateUserTemplateModal',
      props: ['template', 'mode', 'categories'],
      emits: ['updated', 'hidden'],
      data: () => ({ jobIsRunning: false, updateLoading: false }),
      methods: {
        show() {
          showUpdateModal(this.template, this.mode)
        },
      },
      template: '<div class="update-modal" />',
    }),
    DeleteUserTemplateModal: defineComponent({
      name: 'DeleteUserTemplateModal',
      props: ['template'],
      emits: ['deleted', 'hidden'],
      methods: {
        show() {
          showDeleteModal(this.template)
        },
      },
      template: '<div class="delete-modal" />',
    }),
  }

  let refreshList = vi.fn()
  let showCreateModal = vi.fn()
  let showUpdateModal = vi.fn()
  let showDeleteModal = vi.fn()
  let removeFromList = vi.fn()

  const mountAndShow = async (...args) => {
    const wrapper = await testApp.mount(TemplateModal, {
      props: { workspace: { id: 1 } },
      global: { stubs, mocks },
    })
    await wrapper.vm.show(...args)
    await flushPromises()
    return wrapper
  }

  it('opens the list, a template from it and goes back', async () => {
    const wrapper = await mountAndShow()

    expect(wrapper.find('.details').exists()).toBe(false)
    expect(wrapper.find('.list').isVisible()).toBe(true)

    await wrapper.find('.list__recipe-book').trigger('click')

    expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')
    expect(wrapper.find('.list').isVisible()).toBe(false)

    await wrapper.find('.details__back').trigger('click')

    expect(wrapper.find('.details').exists()).toBe(false)
    expect(wrapper.find('.list').isVisible()).toBe(true)
  })

  it('opens the template with the given id or slug right away', async () => {
    let wrapper = await mountAndShow(2)
    expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')

    wrapper = await mountAndShow('project-tracker')
    expect(wrapper.find('.details').text()).toBe('Project Tracker: Business')
  })

  it('opens the default template right away', async () => {
    testApp.mock.resetHandlers()
    testApp.mock.onGet('/templates/').reply(200, [
      { ...categories[0], templates: [projectTracker] },
      { ...categories[1], templates: [{ ...recipeBook, is_default: true }] },
    ])
    const wrapper = await mountAndShow()

    expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')

    await wrapper.find('.details__back').trigger('click')

    expect(wrapper.find('.list').isVisible()).toBe(true)
  })

  it('opens the list again when shown after a template was opened', async () => {
    const wrapper = await mountAndShow('project-tracker')

    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.find('.details').exists()).toBe(false)
    expect(wrapper.find('.list').isVisible()).toBe(true)
  })

  it('lets the list claim the search shortcut only while it is shown', async () => {
    const wrapper = await mountAndShow()
    const list = () => wrapper.findComponent({ name: 'TemplateList' })

    expect(list().props('active')).toBe(true)

    await wrapper.find('.list__recipe-book').trigger('click')
    expect(list().props('active')).toBe(false)

    await wrapper.find('.details__back').trigger('click')
    expect(list().props('active')).toBe(true)

    // The list stays mounted while the modal is closed.
    await wrapper.vm.hide()
    expect(list().exists()).toBe(true)
    expect(list().props('active')).toBe(false)
  })

  it('closes the template however the modal is hidden', async () => {
    const wrapper = await mountAndShow('project-tracker')

    // Like escape or a click outside, which the modal handles itself.
    wrapper.findComponent({ name: 'Modal' }).vm.$emit('hidden')
    await flushPromises()

    expect(wrapper.find('.details').exists()).toBe(false)
  })

  it('keeps the search shortcut from the page behind it while open', async () => {
    const wrapper = await mountAndShow()
    const { $priorityBus } = wrapper.vm
    const pageSearch = vi.fn()
    $priorityBus.$on('start-search', $priorityBus.level.LOW, pageSearch)
    const startSearch = () => {
      const event = { preventDefault: vi.fn() }
      $priorityBus.$emit('start-search', { event })
      return event
    }

    try {
      await wrapper.find('.list__recipe-book').trigger('click')
      expect(startSearch().preventDefault).toHaveBeenCalled()
      expect(pageSearch).not.toHaveBeenCalled()

      await wrapper.vm.hide()
      startSearch()
      expect(pageSearch).toHaveBeenCalledTimes(1)
    } finally {
      $priorityBus.$off('start-search', pageSearch)
    }
  })

  describe('tabs', () => {
    const tabs = (wrapper) => wrapper.findAll('.segment-control__button')
    const ownList = (wrapper) => wrapper.find('.own-list')

    const openOwnTab = async (wrapper) => {
      await tabs(wrapper)[1].trigger('click')
      await flushPromises()
    }

    // Answers the own templates with the given ones, the rest with the
    // categories.
    const mockOwnTemplates = (results) =>
      testApp.mock
        .onGet('/templates/')
        .reply(({ params }) =>
          params?.owned
            ? [
                200,
                { count: results.length, next: null, previous: null, results },
              ]
            : [200, categories]
        )

    it('are hidden for anonymous users', async () => {
      const wrapper = await mountAndShow()

      expect(tabs(wrapper)).toHaveLength(0)
      expect(ownList(wrapper).exists()).toBe(false)
    })

    it('are hidden while the feature flag is off', async () => {
      testApp.authenticate({ id: 1 })
      mocks = { $featureFlagIsEnabled: () => false }
      const wrapper = await mountAndShow()

      expect(tabs(wrapper)).toHaveLength(0)
    })

    it('switch between the official and the own templates', async () => {
      testApp.authenticate({ id: 1 })
      const wrapper = await mountAndShow()

      expect(tabs(wrapper).map((tab) => tab.text())).toStrictEqual([
        'templateModal.officialTemplates',
        'templateModal.yourTemplates',
      ])
      // The own templates are only loaded when their tab is opened.
      expect(ownList(wrapper).exists()).toBe(false)

      await openOwnTab(wrapper)

      expect(ownList(wrapper).isVisible()).toBe(true)
      expect(wrapper.find('.list').isVisible()).toBe(false)
      expect(
        wrapper.findComponent({ name: 'UserTemplateList' }).props('active')
      ).toBe(true)
      expect(
        wrapper.findComponent({ name: 'TemplateList' }).props('active')
      ).toBe(false)

      await tabs(wrapper)[0].trigger('click')

      expect(wrapper.find('.list').isVisible()).toBe(true)
      // Kept mounted, so that it doesn't load again.
      expect(ownList(wrapper).isVisible()).toBe(false)
    })

    it('open an own template with its categories and go back', async () => {
      testApp.authenticate({ id: 1 })
      const wrapper = await mountAndShow()
      await openOwnTab(wrapper)

      await wrapper.find('.own-list__sprint-tracker').trigger('click')

      expect(wrapper.find('.details').text()).toBe('Sprint Tracker: Agile')
      expect(ownList(wrapper).isVisible()).toBe(false)

      await wrapper.find('.details__back').trigger('click')

      expect(ownList(wrapper).isVisible()).toBe(true)
      expect(wrapper.find('.list').isVisible()).toBe(false)
    })

    it('create a template and list it', async () => {
      testApp.authenticate({ id: 1 })
      const wrapper = await mountAndShow()
      await openOwnTab(wrapper)
      const ownListComponent = () =>
        wrapper.findComponent({ name: 'UserTemplateList' })
      const createModal = wrapper.findComponent({
        name: 'CreateUserTemplateModal',
      })

      expect(createModal.props('categories')).toStrictEqual(categories)

      await wrapper.find('.own-list__create').trigger('click')

      expect(showCreateModal).toHaveBeenCalledTimes(1)
      // The create modal takes the search shortcut.
      expect(ownListComponent().props('active')).toBe(false)

      createModal.vm.$emit('created', { id: 9, template: 3 })
      createModal.vm.$emit('hidden')
      await flushPromises()

      expect(refreshList).toHaveBeenCalledTimes(1)
      expect(ownListComponent().props('active')).toBe(true)
    })

    it('update an own template from the list', async () => {
      testApp.authenticate({ id: 1 })
      const wrapper = await mountAndShow()
      await openOwnTab(wrapper)
      const ownListComponent = () =>
        wrapper.findComponent({ name: 'UserTemplateList' })

      await wrapper.find('.own-list__edit').trigger('click')
      await flushPromises()

      expect(showUpdateModal).toHaveBeenCalledWith(sprintTracker, 'content')
      const updateModal = wrapper.findComponent({
        name: 'UpdateUserTemplateModal',
      })
      expect(updateModal.props('categories')).toStrictEqual(categories)
      // The update modal takes the search shortcut.
      expect(ownListComponent().props('active')).toBe(false)

      updateModal.vm.$emit('updated', { id: 9, template: 2 })
      updateModal.vm.$emit('hidden')
      await flushPromises()

      expect(refreshList).toHaveBeenCalledTimes(1)
      expect(ownListComponent().props('active')).toBe(true)
    })

    it('update an own template from its preview, which shows the new revision', async () => {
      testApp.authenticate({ id: 1 })
      const updated = { ...sprintTracker, name: 'Sprints', workspace_id: 202 }
      // Another template was updated after it in the meantime.
      const recipeTracker = { ...sprintTracker, id: 3, name: 'Recipe Tracker' }
      mockOwnTemplates([recipeTracker, updated])
      const wrapper = await mountAndShow()
      await openOwnTab(wrapper)
      await wrapper.find('.own-list__sprint-tracker').trigger('click')
      const details = wrapper.findComponent({ name: 'TemplateDetails' })

      expect(details.props('isOwn')).toBe(true)

      await wrapper.find('.details__edit').trigger('click')
      await flushPromises()

      expect(showUpdateModal).toHaveBeenCalledWith(sprintTracker, 'details')

      wrapper
        .findComponent({ name: 'UpdateUserTemplateModal' })
        .vm.$emit('updated', { id: 9, template: 2 })
      await flushPromises()

      expect(refreshList).toHaveBeenCalledTimes(1)
      expect(wrapper.find('.details').text()).toBe('Sprints: Agile')
      // Mounted again, so that the preview loads the new workspace.
      const newDetails = wrapper.findComponent({ name: 'TemplateDetails' })
      expect(newDetails.vm).not.toBe(details.vm)
      expect(newDetails.props('template')).toStrictEqual(updated)
    })

    it('reload an own template whose install was refused as it was updated', async () => {
      testApp.authenticate({ id: 1 })
      // Updated in another tab after its preview was opened.
      const updated = {
        ...sprintTracker,
        name: 'Sprints',
        workspace_id: 202,
        revision_id: 12,
      }
      mockOwnTemplates([updated])
      const wrapper = await mountAndShow()
      await openOwnTab(wrapper)
      await wrapper.find('.own-list__sprint-tracker').trigger('click')
      const details = wrapper.findComponent({ name: 'TemplateDetails' })

      await wrapper.find('.details__outdated').trigger('click')
      await flushPromises()

      expect(refreshList).toHaveBeenCalledTimes(1)
      expect(wrapper.find('.details').text()).toBe('Sprints: Agile')
      // Mounted again, so that the preview loads the new revision.
      const newDetails = wrapper.findComponent({ name: 'TemplateDetails' })
      expect(newDetails.vm).not.toBe(details.vm)
      expect(newDetails.props('template')).toStrictEqual(updated)
    })

    it('show the running update again instead of updating another template', async () => {
      testApp.authenticate({ id: 1 })
      const recipeTracker = { ...sprintTracker, id: 3, name: 'Recipe Tracker' }
      const wrapper = await mountAndShow()
      await openOwnTab(wrapper)
      await wrapper.find('.own-list__edit').trigger('click')
      await flushPromises()
      const updateModal = wrapper.findComponent({
        name: 'UpdateUserTemplateModal',
      })
      updateModal.vm.jobIsRunning = true
      updateModal.vm.$emit('hidden')

      await wrapper.vm.openUpdateModal(recipeTracker, 'details')
      await flushPromises()

      // The modal monitoring the running update stays mounted.
      expect(showUpdateModal).toHaveBeenLastCalledWith(sprintTracker, 'content')
      expect(wrapper.vm.updating).toBe(true)
      expect(
        wrapper.findComponent({ name: 'UpdateUserTemplateModal' }).vm
      ).toBe(updateModal.vm)

      // Also while the update is being sent, before its job is known.
      updateModal.vm.jobIsRunning = false
      updateModal.vm.updateLoading = true
      await wrapper.vm.openUpdateModal(recipeTracker, 'details')
      await flushPromises()

      expect(showUpdateModal).toHaveBeenLastCalledWith(sprintTracker, 'content')
      expect(
        wrapper.findComponent({ name: 'UpdateUserTemplateModal' }).vm
      ).toBe(updateModal.vm)

      updateModal.vm.updateLoading = false
      await wrapper.vm.openUpdateModal(recipeTracker, 'details')
      await flushPromises()

      expect(showUpdateModal).toHaveBeenLastCalledWith(recipeTracker, 'details')
    })

    describe('delete', () => {
      const deleteModal = (wrapper) =>
        wrapper.findComponent({ name: 'DeleteUserTemplateModal' })
      const ownListComponent = (wrapper) =>
        wrapper.findComponent({ name: 'UserTemplateList' })

      it('an own template from the list and drop it', async () => {
        testApp.authenticate({ id: 1 })
        const wrapper = await mountAndShow()
        await openOwnTab(wrapper)

        expect(deleteModal(wrapper).exists()).toBe(false)

        await wrapper.find('.own-list__delete').trigger('click')
        await flushPromises()

        expect(showDeleteModal).toHaveBeenCalledWith(sprintTracker)
        // The delete modal takes the search shortcut.
        expect(ownListComponent(wrapper).props('active')).toBe(false)

        deleteModal(wrapper).vm.$emit('deleted', sprintTracker.id, false, 12.5)
        deleteModal(wrapper).vm.$emit('hidden')
        await flushPromises()

        // When the deletion was asked for, which the list compares with its pages.
        expect(removeFromList).toHaveBeenCalledWith(sprintTracker.id, 12.5)
        expect(refreshList).not.toHaveBeenCalled()
        expect(ownListComponent(wrapper).props('active')).toBe(true)
      })

      it('an own template from its preview, which closes', async () => {
        testApp.authenticate({ id: 1 })
        const wrapper = await mountAndShow()
        await openOwnTab(wrapper)
        await wrapper.find('.own-list__sprint-tracker').trigger('click')

        await wrapper.find('.details__delete').trigger('click')
        await flushPromises()

        expect(showDeleteModal).toHaveBeenCalledWith(sprintTracker)

        deleteModal(wrapper).vm.$emit('deleted', sprintTracker.id)
        await flushPromises()

        expect(removeFromList).toHaveBeenCalledWith(sprintTracker.id, undefined)
        expect(wrapper.find('.details').exists()).toBe(false)
        expect(ownList(wrapper).isVisible()).toBe(true)
      })

      it('keep the preview of another template open', async () => {
        testApp.authenticate({ id: 1 })
        const ownRecipe = { ...sprintTracker, id: 3, name: 'Recipe Tracker' }
        const wrapper = await mountAndShow()
        await openOwnTab(wrapper)
        await wrapper.find('.own-list__delete').trigger('click')
        await flushPromises()

        // Another own template is previewed while the deletion runs.
        wrapper.vm.selectTemplate(ownRecipe, true)
        await flushPromises()
        deleteModal(wrapper).vm.$emit('deleted', sprintTracker.id)
        await flushPromises()

        expect(wrapper.find('.details').text()).toBe('Recipe Tracker: Agile')

        // An official template with the same id isn't the deleted one.
        await wrapper.find('.details__back').trigger('click')
        await tabs(wrapper)[0].trigger('click')
        await wrapper.find('.list__recipe-book').trigger('click')
        deleteModal(wrapper).vm.$emit('deleted', recipeBook.id)
        await flushPromises()

        expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')
      })

      it('close the update modal of the deleted template', async () => {
        testApp.authenticate({ id: 1 })
        const wrapper = await mountAndShow()
        await openOwnTab(wrapper)
        await wrapper.find('.own-list__edit').trigger('click')
        await flushPromises()

        expect(
          wrapper.findComponent({ name: 'UpdateUserTemplateModal' }).exists()
        ).toBe(true)

        await wrapper.find('.own-list__delete').trigger('click')
        await flushPromises()
        deleteModal(wrapper).vm.$emit('deleted', 3)
        await flushPromises()

        // Another template's deletion leaves it.
        expect(
          wrapper.findComponent({ name: 'UpdateUserTemplateModal' }).exists()
        ).toBe(true)

        deleteModal(wrapper).vm.$emit('deleted', sprintTracker.id)
        deleteModal(wrapper).vm.$emit('hidden')
        await flushPromises()

        expect(
          wrapper.findComponent({ name: 'UpdateUserTemplateModal' }).exists()
        ).toBe(false)
        expect(wrapper.vm.updating).toBe(false)
        expect(ownListComponent(wrapper).props('active')).toBe(true)
      })

      // The count of a page loaded after the template was deleted in another tab
      // already leaves it out, so it must not be decremented again.
      it('an own template that was already deleted, which loads the list again', async () => {
        testApp.authenticate({ id: 1 })
        const templates = Array.from({ length: 22 }, (_, i) => ({
          ...sprintTracker,
          id: i + 1,
          slug: `template-${i + 1}`,
          name: `Template ${i + 1}`,
          state: 'private',
        }))
        const remaining = templates.filter(({ id }) => id !== 5)
        const ownPages = [
          { count: 22, results: templates.slice(0, 20) },
          // Template 5 was deleted in another tab before this page loaded.
          { count: 21, results: remaining.slice(20) },
          { count: 21, results: remaining.slice(0, 20) },
        ]
        testApp.mock.resetHandlers()
        testApp.mock
          .onGet('/templates/')
          .reply((config) =>
            config.params?.type === 'user'
              ? [200, ownPages.shift()]
              : [200, categories]
          )
        const realListStubs = Object.fromEntries(
          Object.entries(stubs).filter(([name]) => name !== 'UserTemplateList')
        )
        const wrapper = await testApp.mount(TemplateModal, {
          props: { workspace: { id: 1 } },
          global: { stubs: realListStubs, mocks },
        })
        await wrapper.vm.show()
        await flushPromises()
        await openOwnTab(wrapper)
        wrapper.findComponent(InfiniteScroll).vm.$emit('load-next-page', 2)
        await flushPromises()
        const title = () => wrapper.find('.user-template-list__title').text()

        expect(title()).toBe('userTemplateList.count - 21')

        // Its preview is open and the deletion in this tab answers 404.
        wrapper.vm.selectTemplate(templates[4], true)
        await flushPromises()
        await wrapper.find('.details__delete').trigger('click')
        deleteModal(wrapper).vm.$emit('deleted', 5, true)
        await flushPromises()

        expect(wrapper.find('.details').exists()).toBe(false)
        expect(wrapper.find('.user-template-list').isVisible()).toBe(true)

        const names = wrapper
          .findAll('.user-template-list__name-title')
          .map((el) => el.text())
        expect(names).not.toContain('Template 5')
        // 21 templates are left on the server.
        expect(title()).toBe('userTemplateList.count - 21')
        expect(ownPages).toHaveLength(0)
      })
    })

    it("don't update an official template", async () => {
      testApp.authenticate({ id: 1 })
      const wrapper = await mountAndShow()
      await openOwnTab(wrapper)
      await wrapper.find('.own-list__sprint-tracker').trigger('click')
      await wrapper.find('.details__back').trigger('click')
      await tabs(wrapper)[0].trigger('click')

      await wrapper.find('.list__recipe-book').trigger('click')

      expect(
        wrapper.findComponent({ name: 'TemplateDetails' }).props('isOwn')
      ).toBe(false)
    })

    it('start at the official templates when shown again', async () => {
      testApp.authenticate({ id: 1 })
      const wrapper = await mountAndShow()
      await openOwnTab(wrapper)

      await wrapper.vm.show()
      await flushPromises()

      expect(wrapper.find('.list').isVisible()).toBe(true)
      expect(ownList(wrapper).exists()).toBe(false)
    })
  })
})
