import { mountSuspended } from '@nuxt/test-utils/runtime'

import HTTPResponsePicker from '@baserow/modules/integrations/core/components/services/HTTPResponsePicker'

const mountComponent = (props) =>
  mountSuspended(HTTPResponsePicker, {
    props,
    global: { mocks: { $t: (key) => key } },
  })

const findRows = (wrapper, label) =>
  wrapper
    .findAll('.http-response-picker__row')
    .filter(
      (row) => row.find('.http-response-picker__key').text() === `${label}`
    )

const findRow = (wrapper, label) => findRows(wrapper, label)[0]

const rowTag = (row) => row.find('.http-response-picker__tag').text()

const body = {
  data: { items: [{ id: 1, name: 'Lamp' }], total: 1 },
  meta: { 'page.size': 20 },
}

describe('HTTPResponsePicker', () => {
  test('the whole response is one record, and its only list is suggested', async () => {
    const wrapper = await mountComponent({ response: body })

    expect(rowTag(findRow(wrapper, 'httpResponsePicker.response'))).toBe(
      'httpResponsePicker.oneRecord'
    )
    // The list is shown: the rows above it are open.
    expect(rowTag(findRow(wrapper, 'items'))).toBe(
      'httpResponsePicker.suggested'
    )
    expect(
      findRow(wrapper, 'total').find('.http-response-picker__value').text()
    ).toBe('1')
    // Only the response and its lists can be chosen.
    expect(
      findRow(wrapper, 'total').find('.http-response-picker__tag').exists()
    ).toBe(false)
  })

  test('choosing a list emits its path', async () => {
    const wrapper = await mountComponent({ response: body })

    await findRow(wrapper, 'items').trigger('click')

    expect(wrapper.emitted('select')).toEqual([
      [{ returnsList: true, listPath: 'data.items' }],
    ])

    await findRow(wrapper, 'httpResponsePicker.response').trigger('click')
    // The response is already the record.
    expect(wrapper.emitted('select')).toHaveLength(1)
  })

  test('the list at the list path is the records', async () => {
    const wrapper = await mountComponent({
      response: body,
      returnsList: true,
      listPath: 'data.items',
    })

    expect(rowTag(findRow(wrapper, 'items'))).toBe('httpResponsePicker.records')
    expect(rowTag(findRow(wrapper, 'httpResponsePicker.response'))).toBe(
      'httpResponsePicker.select'
    )

    await findRow(wrapper, 'httpResponsePicker.response').trigger('click')
    expect(wrapper.emitted('select')).toEqual([
      [{ returnsList: false, listPath: '' }],
    ])
  })

  test('a response which is a list is suggested as the records', async () => {
    const wrapper = await mountComponent({ response: [{ id: 1 }, { id: 2 }] })
    const root = findRow(wrapper, 'httpResponsePicker.response')

    expect(rowTag(root)).toBe('httpResponsePicker.suggested')

    await root.trigger('click')
    expect(wrapper.emitted('select')).toEqual([
      [{ returnsList: true, listPath: '' }],
    ])
  })

  test('opens rows, and lists under a key with a dot cannot be chosen', async () => {
    const wrapper = await mountComponent({
      response: { 'a.b': { rows: [1] }, pages: [{ rows: [2] }] },
    })

    expect(findRow(wrapper, 'rows')).toBeUndefined()
    await findRow(wrapper, 'a.b').trigger('click')
    const dottedRows = findRow(wrapper, 'rows')
    expect(dottedRows.find('.http-response-picker__tag').exists()).toBe(false)
    await dottedRows.trigger('click')
    expect(wrapper.emitted('select')).toBeUndefined()

    // A list in a list is chosen by the position of the item it's in.
    await findRow(wrapper, 'pages').find('button').trigger('click')
    await findRows(wrapper, 0).at(-1).find('button').trigger('click')
    await findRows(wrapper, 'rows').at(-1).trigger('click')
    expect(wrapper.emitted('select')).toEqual([
      [{ returnsList: true, listPath: 'pages.0.rows' }],
    ])
  })

  test('can be used with the keyboard', async () => {
    const wrapper = await mountComponent({ response: body })
    const meta = findRow(wrapper, 'meta')

    // Every row can be reached with tab, and its toggle is named.
    const rows = wrapper.findAll('.http-response-picker__row')
    expect(rows.map((row) => row.attributes('tabindex'))).toEqual(
      rows.map(() => '0')
    )
    expect(meta.attributes('aria-expanded')).toBe('false')
    expect(meta.find('button').attributes('tabindex')).toBe('-1')
    expect(meta.find('button').attributes('aria-label')).toBe(
      'httpResponsePicker.expand'
    )

    // The arrows open and close a row.
    await meta.trigger('keydown', { key: 'ArrowRight' })
    expect(findRow(wrapper, 'meta').attributes('aria-expanded')).toBe('true')
    expect(findRow(wrapper, 'page.size')).toBeDefined()
    await findRow(wrapper, 'meta').trigger('keydown', { key: 'ArrowLeft' })
    expect(findRow(wrapper, 'page.size')).toBeUndefined()

    // Enter and space choose a row.
    await findRow(wrapper, 'items').trigger('keydown', { key: 'Enter' })
    await wrapper.setProps({ returnsList: true, listPath: 'data.items' })
    await findRow(wrapper, 'httpResponsePicker.response').trigger('keydown', {
      key: ' ',
    })
    expect(wrapper.emitted('select')).toEqual([
      [{ returnsList: true, listPath: 'data.items' }],
      [{ returnsList: false, listPath: '' }],
    ])
    expect(findRow(wrapper, 'items').attributes('aria-selected')).toBe('true')
  })
})
