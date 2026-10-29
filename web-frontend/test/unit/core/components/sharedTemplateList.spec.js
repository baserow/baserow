import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import { heldBack } from '@baserow/test/helpers/heldBack'
import SharedTemplateList from '@baserow/modules/core/components/template/SharedTemplateList'
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
  state: null,
  ...extra,
})

const page = (templates, nextCursor = null) => ({
  count: templates.length,
  next: null,
  previous: null,
  results: templates,
  next_cursor: nextCursor,
})

describe('SharedTemplateList', () => {
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

  beforeEach(() => {
    testApp = new TestApp()
    requests = []
    // Registered first, so that the pages don't answer it.
    testApp.mock
      .onGet('/templates/', { params: { view: 'listed_categories' } })
      .reply(200, [{ id: 7, name: 'Agile' }])
  })

  afterEach(async () => {
    vi.useRealTimers()
    await testApp.afterEach()
  })

  const mountComponent = async () => {
    const wrapper = await testApp.mount(SharedTemplateList)
    await flushPromises()
    return wrapper
  }

  test('shows the author, "You" for own templates, and the categories in use', async () => {
    mockPages(
      page([
        listed(1, 'Sprint Tracker', { state: 'public' }),
        listed(2, 'Launch Plan'),
        listed(3, 'Orphan', { author_name: null }),
      ])
    )
    const wrapper = await mountComponent()

    const cards = wrapper.findAll('.template-list__card')
    expect(
      cards.map((card) => [
        card.find('.template-list__card-name').text(),
        card.find('.shared-template-list__author-name').exists()
          ? card.find('.shared-template-list__author-name').text()
          : null,
      ])
    ).toStrictEqual([
      ['Sprint Tracker', 'sharedTemplateList.you'],
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
      'sharedTemplateList.errorTitle'
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

  test('loads the first page again with the chosen category and search', async () => {
    const first = Array.from({ length: 20 }, (_, i) => listed(i + 1, `T${i}`))
    mockPages(
      page(first, '1_20_20'),
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
      { limit: 20 },
      { cursor: '1_20_20', limit: 20 },
      { limit: 20, category: 7 },
      { limit: 20, category: 7, search: 'board' },
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
        .onGet('/templates/', { params: { view: 'listed_categories' } })
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

    expect(requests.at(-1)).toStrictEqual({ limit: 20 })
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
