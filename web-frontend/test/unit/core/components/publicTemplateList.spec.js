import {
  afterAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import { heldBack } from '@baserow/test/helpers/heldBack'
import PublicTemplateList from '@baserow/modules/core/components/template/PublicTemplateList'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'

const listed = (id, name, extra = {}) => ({
  id,
  type: 'user',
  name,
  slug: `${name.toLowerCase().replace(/ /g, '-')}-a1b2c3`,
  description: `${name} description`,
  icon: 'iconoir-table',
  categories: [],
  author_name: 'Grace',
  install_count: 0,
  is_own: false,
  ...extra,
})

// `hasNext` tells that a next page follows.
const page = (templates, hasNext = false) => ({
  count: templates.length,
  next: hasNext ? 'http://localhost/api/templates/?offset=next' : null,
  previous: null,
  results: templates,
})

const names = (wrapper) =>
  wrapper.findAll('.template-list__card-name').map((name) => name.text())

describe('PublicTemplateList', () => {
  let testApp = null
  let requests = []

  // Replies with the given pages in order and records the query of each request,
  // which always asks for the listed user templates. A page can be a function
  // returning the reply, for example a promise of it.
  const mockPages = (...pages) => {
    pages.forEach((data) => {
      testApp.mock.onGet('/templates/').replyOnce((config) => {
        const { view, type, listed, ...query } = config.params
        expect({ view, type, listed }).toStrictEqual({
          view: 'flat',
          type: 'user',
          listed: true,
        })
        requests.push(query)
        return typeof data === 'function' ? data() : [200, data]
      })
    })
  }

  // jsdom doesn't lay out, so the list is made to scroll unless a test says
  // otherwise. A hidden list (`display: none`) measures 0.
  let scrolls = true
  let hidden = false
  const spyOnSize = (name, size) => {
    let proto = HTMLElement.prototype
    while (!Object.hasOwn(proto, name)) {
      proto = Object.getPrototypeOf(proto)
    }
    return vi.spyOn(proto, name, 'get').mockImplementation(size)
  }
  const scrollHeight = spyOnSize('scrollHeight', () =>
    hidden ? 0 : scrolls ? 1000 : 400
  )
  const clientHeight = spyOnSize('clientHeight', () => (hidden ? 0 : 500))

  beforeEach(() => {
    testApp = new TestApp()
    requests = []
    scrolls = true
    hidden = false
    // Registered first, so that the pages don't answer it.
    testApp.mock
      .onGet('/templates/', { params: { view: 'public_categories' } })
      .reply(200, [{ id: 7, name: 'Agile' }])
  })

  afterEach(async () => {
    vi.useRealTimers()
    await testApp.afterEach()
  })

  afterAll(() => {
    scrollHeight.mockRestore()
    clientHeight.mockRestore()
  })

  const mountComponent = async () => {
    const wrapper = await testApp.mount(PublicTemplateList)
    await flushPromises()
    return wrapper
  }

  test('shows the author, "You" for own templates, and the categories in use', async () => {
    mockPages(
      page([
        listed(1, 'Sprint Tracker', { is_own: true }),
        listed(2, 'Launch Plan'),
        listed(3, 'Orphan', { author_name: null }),
      ])
    )
    const wrapper = await mountComponent()

    const cards = wrapper.findAll('.template-list__card')
    expect(
      cards.map((card) => [
        card.find('.template-list__card-name').text(),
        card.find('.public-template-list__author-name').exists()
          ? card.find('.public-template-list__author-name').text()
          : null,
      ])
    ).toStrictEqual([
      ['Sprint Tracker', 'publicTemplateList.you'],
      ['Launch Plan', 'Grace'],
      ['Orphan', null],
    ])
    expect(
      wrapper
        .findAll('.template-list__category-link')
        .map((link) => link.text())
    ).toStrictEqual(['templateCategories.allTemplates', 'Agile'])

    await cards[1].trigger('click')
    expect(wrapper.emitted('selected')[0][0].id).toBe(2)
  })

  test('shows only the error when the first page fails', async () => {
    mockPages(() => [500, { error: 'ERROR_UNKNOWN', detail: 'Failed.' }])
    const wrapper = await mountComponent()

    expect(wrapper.find('.template-empty-state__title').text()).toBe(
      'publicTemplateList.errorTitle'
    )
    expect(testApp.store.state.toast.items).toHaveLength(0)
  })

  test('shows the templates of the last chosen category only', async () => {
    const all = heldBack()
    mockPages(all.reply, page([listed(30, 'Agile Board')]))
    const wrapper = await mountComponent()

    await wrapper
      .findAll('.template-list__category-link')
      .find((link) => link.text() === 'Agile')
      .trigger('click')
    await flushPromises()
    all.send([200, page([listed(1, 'Sprint Tracker')])])
    await flushPromises()

    expect(
      wrapper.findAll('.template-list__card-name').map((name) => name.text())
    ).toStrictEqual(['Agile Board'])
  })

  test('loads the next page after the received templates, each shown once', async () => {
    const first = Array.from({ length: 20 }, (_, i) => listed(i + 1, `T${i}`))
    mockPages(
      page(first, true),
      // The last template of the first page moved to this one meanwhile.
      page([listed(20, 'T19'), listed(21, 'Next')], true),
      page([listed(22, 'Last')])
    )
    const wrapper = await mountComponent()

    wrapper.findComponent(InfiniteScroll).vm.$emit('load-next-page')
    await flushPromises()
    wrapper.findComponent(InfiniteScroll).vm.$emit('load-next-page')
    await flushPromises()

    expect(requests.map(({ offset }) => offset)).toStrictEqual([0, 20, 22])
    expect(names(wrapper)).toStrictEqual([
      ...first.map(({ name }) => name),
      'Next',
      'Last',
    ])
    expect(wrapper.findComponent(InfiniteScroll).props('hasMorePage')).toBe(
      false
    )
  })

  test('loads the next pages while the templates do not fill the list', async () => {
    scrolls = false
    mockPages(
      page([listed(1, 'First')], true),
      page([listed(2, 'Second')], true),
      page([listed(3, 'Third')])
    )
    const wrapper = await mountComponent()

    expect(requests.map(({ offset }) => offset)).toStrictEqual([0, 1, 2])
    expect(names(wrapper)).toStrictEqual(['First', 'Second', 'Third'])
  })

  test('loads the next pages while hidden only once it is shown again', async () => {
    mockPages(
      page([listed(1, 'First')], true),
      page([listed(1, 'First')], true),
      page([listed(2, 'Second')])
    )
    const wrapper = await mountComponent()

    // A template's preview hides the list, which is refreshed meanwhile.
    hidden = true
    scrolls = false
    await wrapper.setProps({ active: false })
    await wrapper.vm.refresh()
    await flushPromises()
    expect(requests.map(({ offset }) => offset)).toStrictEqual([0, 0])

    hidden = false
    await wrapper.setProps({ active: true })
    await flushPromises()
    expect(requests.map(({ offset }) => offset)).toStrictEqual([0, 0, 1])
    expect(names(wrapper)).toStrictEqual(['First', 'Second'])
  })

  test("doesn't load the next page while the list scrolls", async () => {
    mockPages(page([listed(1, 'First')], true))
    await mountComponent()

    expect(requests).toHaveLength(1)
  })

  test('shows when each template was last updated', async () => {
    mockPages(
      page([
        listed(1, 'Sprint Tracker', { updated_on: '2020-01-01T00:00:00Z' }),
      ])
    )
    const wrapper = await testApp.mount(PublicTemplateList, {
      global: {
        mocks: {
          $t: (key, params) =>
            params ? `${key} ${JSON.stringify(params)}` : key,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('.public-template-list__updated').text()).toMatch(
      /^publicTemplateList\.updated \{"ago":"datetime\.yearsAgo/
    )
  })

  test('loads the first page again with the chosen category and search', async () => {
    const first = Array.from({ length: 20 }, (_, i) => listed(i + 1, `T${i}`))
    mockPages(
      page(first, true),
      page([listed(21, 'Last')]),
      page([listed(30, 'Agile Board')]),
      page([])
    )
    const wrapper = await mountComponent()

    wrapper.findComponent(InfiniteScroll).vm.$emit('load-next-page', 2)
    await flushPromises()
    expect(wrapper.findAll('.template-list__card')).toHaveLength(21)

    const agile = wrapper
      .findAll('.template-list__category-link')
      .find((link) => link.text() === 'Agile')
    await agile.trigger('click')
    await flushPromises()

    vi.useFakeTimers()
    await wrapper.find('.template-list__search input').setValue('board')
    await vi.runAllTimersAsync()
    await flushPromises()

    expect(requests).toStrictEqual([
      { offset: 0, limit: 20 },
      { offset: 20, limit: 20 },
      { offset: 0, limit: 20, category: 7 },
      { offset: 0, limit: 20, category: 7, search: 'board' },
    ])
    expect(wrapper.find('.template-empty-state__icon i').classes()).toContain(
      'iconoir-search'
    )
  })

  test('shows all templates once the chosen category is gone', async () => {
    const stale = heldBack()
    testApp.mock.resetHandlers()
    const categories = (reply) =>
      testApp.mock
        .onGet('/templates/', { params: { view: 'public_categories' } })
        .replyOnce(reply)
    categories(() => [200, [{ id: 7, name: 'Agile' }]])
    categories(stale.reply)
    categories(() => [200, []])
    mockPages(
      page([listed(1, 'Sprint Tracker')]),
      page([listed(30, 'Agile Board')]),
      page([]),
      page([]),
      page([listed(1, 'Sprint Tracker')])
    )
    const wrapper = await mountComponent()
    await wrapper
      .findAll('.template-list__category-link')
      .find((link) => link.text() === 'Agile')
      .trigger('click')
    await flushPromises()

    // The categories of the first refresh answer last.
    wrapper.vm.refresh()
    wrapper.vm.refresh()
    await flushPromises()
    stale.send([200, [{ id: 7, name: 'Agile' }]])
    await flushPromises()

    expect(requests.at(-1)).toStrictEqual({ offset: 0, limit: 20 })
    expect(
      wrapper
        .findAll('.template-list__category-link')
        .map((link) => link.text())
    ).not.toContain('Agile')
    expect(
      wrapper.findAll('.template-list__card-name').map((name) => name.text())
    ).toStrictEqual(['Sprint Tracker'])
  })
})
