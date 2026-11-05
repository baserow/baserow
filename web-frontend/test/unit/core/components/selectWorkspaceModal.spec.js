import { flushPromises } from '@vue/test-utils'

import SelectWorkspaceModal from '@baserow/modules/core/components/admin/workspaces/modals/SelectWorkspaceModal'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('SelectWorkspaceModal', () => {
  let testApp
  let anchor

  beforeEach(() => {
    testApp = new TestApp()
    anchor = document.createElement('button')
    document.body.appendChild(anchor)
  })

  afterEach(async () => {
    await testApp.afterEach()
    anchor.remove()
    vi.restoreAllMocks()
  })

  test('lists all workspace options and prevents selecting an existing workspace', async () => {
    testApp.mock.onGet('/admin/workspaces/options/').reply(200, {
      count: 2,
      results: [
        { id: 1, value: 'Already excluded' },
        { id: 2, value: 'Another workspace' },
      ],
    })
    const wrapper = await testApp.mount(SelectWorkspaceModal, {
      props: { selectedIds: [1] },
    })
    await wrapper.vm.show(anchor)
    await flushPromises()

    const options = wrapper.findAll('.select-workspace-modal__option')
    expect(wrapper.find('[role="dialog"]').attributes('aria-label')).toBe(
      'selectWorkspaceModal.title'
    )
    expect(wrapper.findAll('thead th').map((cell) => cell.text())).toEqual([
      '',
      'workspacesAdminTable.id',
      'workspacesAdminTable.name',
    ])
    const selectedCheckbox = wrapper.find('input[type="checkbox"]')
    expect(selectedCheckbox.element.checked).toBe(true)
    expect(selectedCheckbox.element.disabled).toBe(true)
    expect(
      options.map((option) =>
        option.find('.select-workspace-modal__name').text()
      )
    ).toEqual(['Already excluded', 'Another workspace'])
    expect(options[0].attributes('disabled')).toBeDefined()
    await options[0].trigger('click')
    await wrapper.find('.select-workspace-modal__id').trigger('click')
    expect(wrapper.emitted('selected')).toBeUndefined()

    await options[1].trigger('click')
    expect(wrapper.emitted('selected')).toEqual([
      [{ id: 2, name: 'Another workspace' }],
    ])
    expect(wrapper.emitted('hidden')).toBeUndefined()
    expect(wrapper.find('[role="dialog"]').classes()).not.toContain(
      'visibility-hidden'
    )
    await wrapper.find('.select-workspace-modal__close').trigger('click')
    expect(wrapper.emitted('hidden')).toHaveLength(1)
  })

  test.each(['checkbox', 'id', 'name'])(
    'selects a workspace once through its %s',
    async (target) => {
      testApp.mock.onGet('/admin/workspaces/options/').reply(200, {
        count: 1,
        results: [{ id: 2, value: 'Finance' }],
      })
      const wrapper = await testApp.mount(SelectWorkspaceModal)
      await wrapper.vm.show(anchor)
      await flushPromises()

      if (target === 'checkbox') {
        await wrapper.find('input[type="checkbox"]').setValue(true)
      } else {
        await wrapper
          .find(
            target === 'id'
              ? '.select-workspace-modal__id'
              : '.select-workspace-modal__option'
          )
          .trigger('click')
      }

      expect(wrapper.emitted('selected')).toEqual([
        [{ id: 2, name: 'Finance' }],
      ])
      expect(wrapper.emitted('hidden')).toBeUndefined()
      await wrapper.find('.select-workspace-modal__close').trigger('click')
      expect(wrapper.emitted('hidden')).toHaveLength(1)
    }
  )

  test('anchors above a low button and clamps horizontally near the viewport edge', async () => {
    testApp.mock
      .onGet('/admin/workspaces/options/')
      .reply(200, { count: 1, results: [{ id: 2, value: 'Finance' }] })
    vi.spyOn(anchor, 'getBoundingClientRect').mockReturnValue({
      top: window.innerHeight - 100,
      bottom: window.innerHeight - 72,
      left: window.innerWidth - 60,
      right: window.innerWidth - 32,
      width: 28,
      height: 28,
    })
    const wrapper = await testApp.mount(SelectWorkspaceModal)
    const originalBounds = HTMLElement.prototype.getBoundingClientRect
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
      function () {
        return this.classList.contains('select-workspace-modal')
          ? { width: 520, height: 250 }
          : originalBounds.call(this)
      }
    )

    await wrapper.vm.show(anchor)
    await flushPromises()

    const panel = wrapper.find('[role="dialog"]').element
    expect(panel.style.left).toBe(`${window.innerWidth - 520 - 12}px`)
    expect(panel.style.bottom).toBe('106px')
    expect(panel.style.top).toBe('auto')
    expect(panel.getAttribute('aria-modal')).not.toBe('true')
  })

  test.each(['above', 'below'])(
    'keeps the picker open when selecting moves its anchor %s the viewport',
    async (side) => {
      testApp.mock.onGet('/admin/workspaces/options/').reply(200, {
        count: 1,
        results: [{ id: 2, value: 'Finance' }],
      })
      const bounds = vi.spyOn(anchor, 'getBoundingClientRect').mockReturnValue({
        top: 100,
        bottom: 128,
        left: 100,
        right: 128,
        width: 28,
        height: 28,
      })
      const wrapper = await testApp.mount(SelectWorkspaceModal)
      await wrapper.vm.show(anchor)
      await flushPromises()

      const top = side === 'above' ? -80 : window.innerHeight + 40
      bounds.mockReturnValue({
        top,
        bottom: top + 28,
        left: 100,
        right: 128,
        width: 28,
        height: 28,
      })
      await wrapper.find('.select-workspace-modal__option').trigger('click')
      await flushPromises()

      const panel = wrapper.find('[role="dialog"]')
      expect(panel.classes()).not.toContain('visibility-hidden')
      expect(wrapper.emitted('hidden')).toBeUndefined()
      expect(panel.element.style[side === 'above' ? 'top' : 'bottom']).toBe(
        '18px'
      )
    }
  )

  test('reuses admin pagination and searches from the first page', async () => {
    testApp.mock.onGet('/admin/workspaces/options/').reply((config) => {
      const name = config.params.search || `Page ${config.params.page}`
      return [
        200,
        { count: 101, results: [{ id: config.params.page, value: name }] },
      ]
    })
    const wrapper = await testApp.mount(SelectWorkspaceModal)
    await wrapper.vm.show(anchor)
    await flushPromises()

    await wrapper.findAll('.paginator__button')[1].trigger('click')
    await flushPromises()
    expect(wrapper.find('.select-workspace-modal__option').text()).toContain(
      'Page 2'
    )

    await wrapper.find('.data-table__search input').setValue('Finance')
    await wrapper.find('.data-table__search').trigger('submit')
    await flushPromises()

    expect(testApp.mock.history.get.at(-1).params).toEqual({
      page: 1,
      search: 'Finance',
    })
    expect(wrapper.find('.select-workspace-modal__option').text()).toContain(
      'Finance'
    )
  })
})
