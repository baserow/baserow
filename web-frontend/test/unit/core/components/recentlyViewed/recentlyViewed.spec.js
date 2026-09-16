import { flushPromises } from '@vue/test-utils'
import moment from '@baserow/modules/core/moment'

import { TestApp } from '@baserow/test/helpers/testApp'
import RecentlyViewed from '@baserow/modules/core/components/recentlyViewed/RecentlyViewed'
import RecentlyViewedHeader from '@baserow/modules/core/components/recentlyViewed/RecentlyViewedHeader'

const ACCESS_TOKEN =
  `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImpvaG5AZXhhb` +
  `XBsZS5jb20iLCJpYXQiOjE2NjAyOTEwODYsImV4cCI6MTY2MDI5NDY4NiwianRpIjo` +
  `iNDZmNzUwZWUtMTJhMS00N2UzLWJiNzQtMDIwYWM4Njg3YWMzIiwidXNlcl9pZCI6M` +
  `iwidXNlcl9wcm9maWxlX2lkIjpbMl0sIm9yaWdfaWF0IjoxNjYwMjkxMDg2fQ.RQ-M` +
  `NQdDR9zTi8CbbQkRrwNsyDa5CldQI83Uid1l9So`

const hoursAgo = (hours) => moment().subtract(hours, 'hours').toISOString()

const acme = { id: 1, name: 'Acme' }
const widelab = { id: 2, name: 'Widelab' }

const entries = [
  {
    type: 'database_view',
    sub_type: 'grid',
    last_viewed: hoursAgo(1),
    application: { id: 10, name: 'CRM', type: 'database' },
    workspace: acme,
    item: {
      id: 100,
      name: 'All customers',
      table: { id: 50, name: 'Customers' },
    },
  },
  {
    type: 'builder_page',
    sub_type: null,
    last_viewed: hoursAgo(2),
    application: { id: 11, name: 'Website', type: 'builder' },
    workspace: widelab,
    item: { id: 101, name: 'Landing page' },
  },
  {
    type: 'dashboard',
    sub_type: null,
    last_viewed: hoursAgo(3),
    application: { id: 12, name: 'Q1 Summary', type: 'dashboard' },
    workspace: widelab,
    item: { id: 12, name: 'Q1 Summary' },
  },
  {
    type: 'automation_workflow',
    sub_type: null,
    last_viewed: hoursAgo(4),
    application: { id: 13, name: 'Bots', type: 'automation' },
    workspace: acme,
    item: { id: 102, name: 'Slack notification' },
  },
]

describe('RecentlyViewed', () => {
  let testApp = null

  beforeEach(async () => {
    testApp = new TestApp()
    testApp.store.dispatch('auth/forceSetUserData', {
      user: { id: 1, preferences: {} },
      access_token: ACCESS_TOKEN,
    })
    await testApp.store.dispatch('workspace/forceCreate', {
      ...acme,
      users: [],
    })
    await testApp.store.dispatch('workspace/forceCreate', {
      ...widelab,
      users: [],
    })
    // Translations resolve to their key in tests. The preference endpoint
    // echoes what was stored, like the backend does.
    testApp.mock
      .onPatch('/user/preferences/')
      .reply((config) => [200, JSON.parse(config.data)])
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  function mockItems(results, hasMore = false) {
    testApp.mock
      .onGet('/last-viewed/items/')
      .reply(200, { results, has_more: hasMore })
  }

  async function mount(props = {}) {
    return await testApp.mount(RecentlyViewed, {
      props: {
        title: 'Recently viewed',
        viewModePreferenceKey: 'recently_viewed_view_mode',
        ...props,
      },
    })
  }

  test('renders one row per item with type, parents and workspace', async () => {
    mockItems(entries)
    const wrapper = await mount()

    const rows = wrapper.findAll('.recently-viewed__row')
    expect(rows).toHaveLength(4)
    expect(
      wrapper.find('.recently-viewed__head--with-workspace').exists()
    ).toBe(true)

    const first = rows[0]
    expect(first.find('.recently-viewed__name').text()).toBe('All customers')
    expect(first.find('.recently-viewed__path').text()).toBe(
      'lastViewedItemType.databaseView•CRM›Customers'
    )
    expect(first.find('.item-icon i').classes()).toEqual(
      expect.arrayContaining(['iconoir-menu', 'color-primary'])
    )
    expect(first.find('.recently-viewed__cell--muted').text()).toContain('hour')
    expect(
      first
        .find('.recently-viewed__cell--workspace .recently-viewed__cell-text')
        .text()
    ).toBe('Acme')
    expect(first.find('.avatar__initials').text()).toBe('A')

    expect(rows[1].find('.recently-viewed__path').text()).toBe(
      'lastViewedItemType.builderPage•Website'
    )
    expect(rows[1].find('.item-icon').classes()).toContain('item-icon--blue')
    expect(rows[2].find('.recently-viewed__path').text()).toBe(
      'lastViewedItemType.dashboard'
    )
    expect(rows[3].find('.item-icon').classes()).toContain('item-icon--yellow')
    expect(wrapper.find('.recently-viewed__footer').exists()).toBe(false)

    const request = testApp.mock.history.get[0]
    expect(request.params).toEqual({ limit: 20, offset: 0 })
  })

  test('scopes to the given workspace and hides its column and filter', async () => {
    mockItems(entries.slice(0, 1))
    const wrapper = await mount({ workspace: acme, title: 'Your items' })

    expect(wrapper.find('.recently-viewed__title').text()).toBe('Your items')
    expect(wrapper.findAll('.recently-viewed__filter')).toHaveLength(1)
    expect(
      wrapper.find('.recently-viewed__head--with-workspace').exists()
    ).toBe(false)
    expect(wrapper.find('.recently-viewed__cell--workspace').exists()).toBe(
      false
    )
    expect(testApp.mock.history.get[0].params).toEqual({
      limit: 20,
      offset: 0,
      workspace_ids: '1',
    })
  })

  test('switches to cards and remembers the choice', async () => {
    mockItems(entries)
    const wrapper = await mount()

    await wrapper.findAll('.segment-control__button')[1].trigger('click')
    await flushPromises()

    expect(wrapper.find('.recently-viewed__table').exists()).toBe(false)
    const cards = wrapper.findAll('.item-card')
    expect(cards).toHaveLength(4)
    expect(cards[0].find('.item-card__name').text()).toBe('All customers')
    expect(cards[0].find('.item-card__meta').text()).toContain(
      'lastViewedItemType.databaseView'
    )
    expect(cards[0].attributes('title')).toBe('CRM › Customers')
    expect(testApp.mock.history.patch[0].data).toBe(
      JSON.stringify({ recently_viewed_view_mode: 'cards' })
    )
  })

  test('loads more pages while the backend has more', async () => {
    mockItems(entries, true)
    const wrapper = await mount()

    const button = wrapper.find('.recently-viewed__footer .button')
    expect(button.exists()).toBe(true)

    testApp.mock.reset()
    testApp.mock.onGet('/last-viewed/items/').reply(200, {
      results: [{ ...entries[0], item: { ...entries[0].item, id: 200 } }],
      has_more: false,
    })
    await button.trigger('click')
    await flushPromises()

    expect(testApp.mock.history.get[0].params).toEqual({ limit: 20, offset: 4 })
    expect(wrapper.findAll('.recently-viewed__row')).toHaveLength(5)
    expect(wrapper.find('.recently-viewed__footer').exists()).toBe(false)
  })

  test('reloads from the start when the filters change', async () => {
    mockItems(entries)
    const wrapper = await mount()
    const header = wrapper.findComponent(RecentlyViewedHeader)

    testApp.mock.reset()
    mockItems([])
    header.vm.$emit('update:types', ['database_view:grid', 'builder_page'])
    header.vm.$emit('update:workspaceIds', [2])
    await flushPromises()

    const last = testApp.mock.history.get.at(-1)
    expect(last.params).toEqual({
      limit: 20,
      offset: 0,
      workspace_ids: '2',
      types: 'database_view:grid,builder_page',
    })
    expect(wrapper.find('.recently-viewed__empty-title').text()).toBe(
      'recentlyViewed.noFilterMatchesTitle'
    )

    testApp.mock.reset()
    mockItems(entries)
    await wrapper.find('.recently-viewed__empty-action').trigger('click')
    await flushPromises()
    expect(testApp.mock.history.get.at(-1).params).toEqual({
      limit: 20,
      offset: 0,
    })
    expect(wrapper.findAll('.recently-viewed__row')).toHaveLength(4)
  })

  test('shows a skeleton while the filters reload the list', async () => {
    mockItems(entries)
    const wrapper = await mount()
    const header = wrapper.findComponent(RecentlyViewedHeader)

    let respond = null
    testApp.mock.reset()
    testApp.mock.onGet('/last-viewed/items/').reply(
      () =>
        new Promise((resolve) => {
          respond = () => resolve([200, { results: entries, has_more: false }])
        })
    )
    header.vm.$emit('update:types', ['builder_page'])
    await flushPromises()

    expect(
      wrapper
        .find('.recently-viewed__row:not(.recently-viewed__row--skeleton)')
        .exists()
    ).toBe(false)
    expect(wrapper.findAll('.recently-viewed__row--skeleton')).toHaveLength(4)
    expect(wrapper.find('.skeleton .recently-viewed__head').exists()).toBe(true)
    // The filters stay usable while loading.
    expect(wrapper.findAll('.recently-viewed__filter')).toHaveLength(2)

    respond()
    await flushPromises()
    expect(wrapper.find('.recently-viewed__row--skeleton').exists()).toBe(false)
    expect(wrapper.findAll('.recently-viewed__row')).toHaveLength(4)
  })

  test('shows the empty state with the host action when nothing was viewed', async () => {
    mockItems([])
    const wrapper = await testApp.mount(RecentlyViewed, {
      props: {
        title: 'Recently viewed',
        viewModePreferenceKey: 'recently_viewed_view_mode',
      },
      slots: { 'empty-action': '<button class="host-action">Add</button>' },
    })

    expect(wrapper.find('.recently-viewed__empty-title').text()).toBe(
      'recentlyViewed.emptyTitle'
    )
    expect(wrapper.find('.host-action').exists()).toBe(true)
  })
})
