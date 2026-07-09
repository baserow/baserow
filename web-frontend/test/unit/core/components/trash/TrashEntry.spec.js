import TrashEntry from '@baserow/modules/core/components/trash/TrashEntry'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('TrashEntry component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const trashEntry = (overrides = {}) => ({
    user_who_trashed: 'staff-dev',
    trash_item_type: 'integration',
    trash_item_id: 41,
    name: 'Integration',
    names: null,
    parent_name: 'My App',
    trashed_at: '2024-01-01T00:00:00Z',
    loading: false,
    ...overrides,
  })

  const mountComponent = (entry) =>
    testApp.mount(TrashEntry, { props: { trashEntry: entry } })

  // A name (including its parent context) longer than the 40 char trim threshold.
  const longName = 'Local Baserow (41) inside Untitled Application (79)'

  test('a short name is shown without a "more" toggle', async () => {
    const wrapper = await mountComponent(trashEntry({ name: 'Short name' }))

    expect(wrapper.find('.trash-entry__name-more').exists()).toBe(false)
  })

  test('a name longer than the trim threshold shows a "more" toggle', async () => {
    const wrapper = await mountComponent(trashEntry({ name: longName }))

    const more = wrapper.find('.trash-entry__name-more')
    expect(more.exists()).toBe(true)
    expect(more.text()).toBe('trashEntry.showMore')
  })

  test('clicking "more" toggles the anchor to "less"', async () => {
    const wrapper = await mountComponent(trashEntry({ name: longName }))

    await wrapper.find('.trash-entry__name-more').trigger('click')

    expect(wrapper.find('.trash-entry__name-more').text()).toBe(
      'trashEntry.showLess'
    )
  })
})
