import { TestApp } from '@baserow/test/helpers/testApp'
import RecordSelectorElement from '@baserow/modules/builder/components/elements/components/RecordSelectorElement.vue'
import flushPromises from 'flush-promises'

// Ignore `notifyIf` and `notifyIf404` function calls
jest.mock('@baserow/modules/core/utils/error.js')

describe('RecordSelectorElement', () => {
  let testApp = null
  let store = null
  let mockServer = null

  beforeAll(() => {
    // NOTE: TestApp wraps any exception raised by the axios mock adapter and
    // re-raises it as a Jest error.
    // This mutates the error object and make some properties not available.
    // In this case `collectionElement` mixin needs to access the response
    // object when the server returns a 400/404 error, so we disable
    // `failTestOnErrorResponse`.
    testApp = new TestApp()
    testApp.failTestOnErrorResponse = false
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = ({ props = {}, slots = {}, provide = {} }) => {
    return testApp.mount(RecordSelectorElement, {
      propsData: props,
      slots,
      provide,
    })
  }

  test('does not paginate if API returns 400/404', async () => {
    const page = {
      id: 1,
      dataSources: [
        {
          id: 1,
          type: 'local_baserow_list_rows',
          table_id: 1,
          schema: {
            type: 'array',
            items: {
              properties: {
                field_1: {
                  metadata: { primary: true },
                  title: 'Name',
                },
                field_2: { metadata: {}, title: 'Other' },
              },
            },
          },
        },
      ],
      elements: [],
    }
    const sharedPage = {
      id: 2,
      dataSources: [],
      elements: [],
      shared: true,
    }
    const builder = {
      id: 1,
      theme: { primary_color: '#ccc' },
      pages: [sharedPage, page],
    }
    const workspace = {}
    const mode = 'public'
    const element = {
      id: 1,
      type: 'record_selector',
      data_source_id: page.dataSources[0].id,
      items_per_page: 5,
      page_id: page.id,
    }
    store.dispatch('element/forceCreate', { page, element })

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        currentPage: page,
        elementPage: page,
        mode,
        applicationContext: { builder, page, mode },
        element,
        workspace,
      },
    })

    // A mock server that mimics the data source dispatch endpoints.
    // The first time it is called it returns a successful message, but the
    // second time it returns a 400 response.
    const url = `builder/domains/published/data-source/${page.dataSources[0].id}/dispatch/`
    mockServer.mock
      .onPost(url)
      .replyOnce(200, {
        results: [
          { id: 1, order: 1, Name: 'First' },
          { id: 2, order: 1, Name: 'Second' },
          { id: 3, order: 1, Name: 'Third' },
          { id: 4, order: 1, Name: 'Fourth' },
          { id: 5, order: 1, Name: 'Fifth' },
        ],
        has_next_page: true,
      })
      .onPost(url)
      .reply(400, { message: 'Bad Request' })

    // The first time we trigger a next page, the server responds with 200
    // therefore we should be able to fetch more content
    await wrapper
      .findAllComponents({ name: 'ABDropdown' })
      .at(0)
      .find('.ab-dropdown__selected')
      .trigger('click')
    await flushPromises()
    expect(wrapper.element).toMatchSnapshot()
    expect(mockServer.mock.history.post.length).toBe(1)

    // Then we trigger a few scroll events in the record selector element and
    // confirm that the API is only called once
    await wrapper
      .findAllComponents({ name: 'ABDropdown' })
      .at(0)
      .find('.select__items')
      .trigger('scroll')
    await flushPromises()
    expect(wrapper.element).toMatchSnapshot()
    expect(mockServer.mock.history.post.length).toBe(2)

    await wrapper
      .findAllComponents({ name: 'ABDropdown' })
      .at(0)
      .find('.select__items')
      .trigger('scroll')
    await flushPromises()
    expect(wrapper.element).toMatchSnapshot()
    expect(mockServer.mock.history.post.length).toBe(2)
  })

  test('resolves suffix formulas', async () => {
    const page = {
      id: 1,
      dataSources: [
        {
          id: 1,
          type: 'local_baserow_list_rows',
          table_id: 1,
          schema: {
            type: 'array',
            items: {
              properties: {
                field_1: {
                  metadata: { primary: true },
                  title: 'Name',
                },
                field_2: { metadata: {}, title: 'Other' },
              },
            },
          },
        },
      ],
      elements: [],
    }
    const sharedPage = {
      id: 2,
      dataSources: [],
      elements: [],
      shared: true,
    }
    const builder = {
      id: 1,
      theme: { primary_color: '#ccc' },
      pages: [sharedPage, page],
      selectedElement: null,
    }
    const workspace = {}
    const mode = 'public'
    const element = {
      id: 1,
      type: 'record_selector',
      data_source_id: page.dataSources[0].id,
      items_per_page: 5,
      option_name_suffix: { formula: "'Suffix'", mode: 'simple' },
      page_id: page.id,
    }
    store.dispatch('element/forceCreate', { page, element })

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        currentPage: page,
        elementPage: page,
        mode,
        applicationContext: { builder, page, mode, element },
        element,
        workspace,
      },
    })

    // A simple mock server that return ids and some fields
    const url = `builder/domains/published/data-source/${page.dataSources[0].id}/dispatch/`
    mockServer.mock.onPost(url).reply(200, {
      results: [
        { id: 1, order: 1, Name: 'First', Other: 'One' },
        { id: 2, order: 1, Name: 'Second', Other: 'Two' },
      ],
      has_next_page: false,
    })

    // Check that the literal string was added to all items in the record selector
    await wrapper
      .findAllComponents({ name: 'ABDropdown' })
      .at(0)
      .find('.ab-dropdown__selected')
      .trigger('click')

    await flushPromises()

    expect(wrapper.element).toMatchSnapshot()
    expect(wrapper.find("span[title='First - Suffix']").exists()).toBeTruthy()
    expect(wrapper.find("span[title='Second - Suffix']").exists()).toBeTruthy()

    // Set a formula for suffix and check it was properly resolved
    store.dispatch('element/forceUpdate', {
      builder,
      page,
      element,
      values: {
        option_name_suffix: { formula: "get('current_record.field_2')" },
      },
    })
    await flushPromises()
    await wrapper
      .findAllComponents({ name: 'ABDropdown' })
      .at(0)
      .find('.ab-dropdown__selected')
      .trigger('click')
    await flushPromises()
    expect(wrapper.element).toMatchSnapshot()
    expect(wrapper.find("span[title='First - One']").exists()).toBeTruthy()
    expect(wrapper.find("span[title='Second - Two']").exists()).toBeTruthy()
  })
})
