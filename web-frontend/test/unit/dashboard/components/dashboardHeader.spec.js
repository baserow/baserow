import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardHeader from '@baserow/modules/dashboard/components/DashboardHeader'

const { hasPermission } = vi.hoisted(() => ({ hasPermission: vi.fn() }))
vi.mock('#app', async (importOriginal) => {
  const original = await importOriginal()
  return {
    ...original,
    useNuxtApp: (...args) =>
      new Proxy(original.useNuxtApp(...args), {
        get: (app, key) =>
          key === '$hasPermission' ? hasPermission : app[key],
      }),
  }
})

let testApp
beforeEach(() => {
  hasPermission.mockReturnValue(true)
  testApp = new TestApp()
})
afterEach(async () => {
  await testApp.afterEach()
  vi.restoreAllMocks()
})

async function render(props = {}) {
  return testApp.mount(DashboardHeader, {
    props: {
      dashboard: { id: 1, workspace: { id: 1 } },
      loading: false,
      ...props,
    },
  })
}

async function openMenu(wrapper) {
  await wrapper.get('.dashboard-add-element__trigger').trigger('click')
  await flushPromises()
  return testApp.body.get('.dashboard-add-element__context')
}

test('opens the existing widget picker from the shared menu and forwards selection', async () => {
  const wrapper = await render()
  const menu = await openMenu(wrapper)
  await menu.get('[data-testid="create-dashboard-widget"]').trigger('click')
  await flushPromises()
  expect(
    testApp.body.get('.dashboard-add-element__context').classes()
  ).toContain('visibility-hidden')
  expect(testApp.body.text()).toContain('createWidgetModal.title')
  await testApp.body.get('.create-widget-card').trigger('click')
  expect(wrapper.emitted('widget-variation-selected')[0][0]).toMatchObject({
    name: 'summaryWidget.name',
    params: {},
  })
})

test.each([
  ['dashboard.create_widget', true, false],
  ['dashboard.create_filter', false, true],
  [null, false, false],
])(
  'limits creation choices to the granted permission: %s',
  async (permission, widget, filter) => {
    hasPermission.mockImplementation((operation) => operation === permission)
    const wrapper = await render()
    expect(wrapper.find('.dashboard-add-element__trigger').exists()).toBe(
      widget || filter
    )
    if (widget || filter) {
      const menu = await openMenu(wrapper)
      expect(
        menu.find('[data-testid="create-dashboard-widget"]').exists()
      ).toBe(widget)
      expect(
        menu.find('[data-testid="create-dashboard-filter"]').exists()
      ).toBe(filter)
    }
  }
)

test.each(['isCreatingWidget', 'isCreatingFilter'])(
  'disables creation while %s',
  async (prop) => {
    const wrapper = await render({ [prop]: true })
    expect(
      wrapper.get('.dashboard-add-element__trigger').element.disabled
    ).toBe(true)
  }
)

test('keeps the shared menu in edit mode and leaves edit mode on Done editing', async () => {
  await testApp.store.dispatch('dashboardApplication/enterEditMode')
  const wrapper = await render()
  expect(wrapper.find('.dashboard-add-element__trigger').exists()).toBe(true)
  const done = wrapper
    .findAll('button')
    .find((button) => button.text() === 'dashboardHeader.doneEditing')
  await done.trigger('click')
  expect(wrapper.text()).toContain('dashboardHeaderMenuItems.editMode')
  expect(wrapper.text()).not.toContain('dashboardHeader.doneEditing')
})

test('hides creation while the dashboard is loading', async () => {
  const wrapper = await render({ loading: true })
  expect(wrapper.find('.dashboard-add-element__trigger').exists()).toBe(false)
})

test('focuses the first choice and returns to the trigger on Escape', async () => {
  const wrapper = await render()
  const menu = await openMenu(wrapper)
  expect(document.activeElement).toBe(
    menu.get('[data-testid="create-dashboard-widget"]').element
  )
  await menu.trigger('keydown', { key: 'Escape' })
  expect(
    testApp.body.get('.dashboard-add-element__context').classes()
  ).toContain('visibility-hidden')
  expect(document.activeElement).toBe(
    wrapper.get('.dashboard-add-element__trigger').element
  )
  expect(
    wrapper.get('.dashboard-add-element__trigger').attributes('aria-expanded')
  ).toBe('false')
})
