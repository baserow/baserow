import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarImportTableContextItem from '@baserow/modules/database/components/sidebar/table/SidebarImportTableContextItem'
import FieldService from '@baserow/modules/database/services/field'

vi.mock('@baserow/modules/database/services/field', () => ({
  default: vi.fn(),
}))

describe('SidebarImportTableContextItem', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.clearAllMocks()
  })

  const database = { id: 1, workspace: { id: 10 } }
  const table = { id: 5, name: 'Cars' }
  const fields = [{ id: 100, name: 'Name', type: 'text' }]

  const mockFetchAll = () => {
    const fetchAll = vi.fn().mockResolvedValue({ data: fields })
    FieldService.mockReturnValue({ fetchAll })
    return fetchAll
  }

  const mountItem = async (props = {}) => {
    const show = vi.fn()
    const wrapper = await testApp.mount(SidebarImportTableContextItem, {
      props: { database, table, ...props },
      global: {
        stubs: {
          ImportFileModal: {
            name: 'ImportFileModal',
            props: ['database', 'table', 'fields'],
            template: '<div />',
            methods: { show },
          },
        },
      },
    })
    return { wrapper, show }
  }

  const importModal = (wrapper) =>
    wrapper.findComponent({ name: 'ImportFileModal' })

  test('fetches fields, emits click, and opens the modal', async () => {
    const fetchAll = mockFetchAll()
    const { wrapper, show } = await mountItem()

    await wrapper.find('a').trigger('click')
    await flushPromises()

    expect(fetchAll).toHaveBeenCalledWith(table.id)
    // The modal reads `field._.type.iconClass`, so the fetched fields must be
    // populated with the store's internal metadata before being passed in.
    const passedFields = importModal(wrapper).props('fields')
    expect(passedFields).toHaveLength(1)
    expect(passedFields[0].id).toBe(100)
    expect(passedFields[0]._?.type).toBeDefined()
    expect(wrapper.emitted('click')).toBeTruthy()
    expect(show).toHaveBeenCalled()
  })

  test('still hides the context menu when fetching fields fails', async () => {
    // Mimic a real API error: it carries a `handler` so notifyIf reports it
    // instead of re-throwing.
    const notifyIfHandler = vi.fn()
    const apiError = Object.assign(new Error('boom'), {
      handler: { notifyIf: notifyIfHandler },
    })
    const fetchAll = vi.fn(() => Promise.reject(apiError))
    FieldService.mockReturnValue({ fetchAll })
    const { wrapper, show } = await mountItem()

    await wrapper.find('a').trigger('click')
    await flushPromises()

    // The error is surfaced, the modal never opens, but the menu still closes.
    expect(notifyIfHandler).toHaveBeenCalled()
    expect(show).not.toHaveBeenCalled()
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  test('does nothing when disabled', async () => {
    const fetchAll = mockFetchAll()
    const { wrapper, show } = await mountItem({ disabled: true })

    await wrapper.find('a').trigger('click')
    await flushPromises()

    expect(fetchAll).not.toHaveBeenCalled()
    expect(show).not.toHaveBeenCalled()
  })

  test('blocks re-entry while a fetch is already in progress', async () => {
    const fetchAll = mockFetchAll()
    const { wrapper } = await mountItem()

    const link = wrapper.find('a')
    // Fire both clicks synchronously, before the resolved fetchAll promise's
    // continuation (which flips loading back off) gets to run as a microtask.
    link.trigger('click')
    link.trigger('click')
    await flushPromises()

    expect(fetchAll).toHaveBeenCalledTimes(1)
  })
})
