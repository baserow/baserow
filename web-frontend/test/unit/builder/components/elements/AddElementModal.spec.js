import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal'
import { PAGE_PLACES } from '@baserow/modules/builder/enums'

const PickerHarness = {
  components: { AddElementModal },
  props: ['page', 'placement'],
  template: `
    <button class="open-picker" @click="$refs.picker.show(placement)">Add element</button>
    <AddElementModal ref="picker" :page="page" />
  `,
}

const elementType = ({
  pagePlace = PAGE_PLACES.CONTENT,
  ...overrides
} = {}) => ({
  name: 'Heading',
  description: 'A heading for the page',
  image: '',
  getType: () => 'heading',
  category: () => 'baseElement',
  getPagePlace: () => pagePlace,
  isDisallowedReason: () => '',
  getDeactivatedClickModal: () => null,
  ...overrides,
})

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(async () => {
  vi.restoreAllMocks()
  await testApp.afterEach()
})

async function openPicker({
  placement = {},
  type = elementType(),
  open = true,
} = {}) {
  const heading = { id: 100, page_id: 20, type: 'heading' }
  const container = { id: 200, page_id: 20, type: 'column' }
  const child = { id: 201, page_id: 20, type: 'heading' }
  const header = { id: 301, page_id: 21, type: 'header' }
  const page = {
    id: 20,
    shared: false,
    elementMap: { 100: heading, 200: container, 201: child },
    graph: {
      0: 100,
      100: { next: { '': [200] } },
      200: { children: { 1: [201] } },
      201: {},
    },
  }
  const sharedPage = {
    id: 21,
    shared: true,
    elementMap: { 301: header },
    graph: { 0: 301, 301: {} },
  }
  const builder = { id: 10, pages: [page, sharedPage] }
  const getAll = testApp.$registry.getAll.bind(testApp.$registry)
  vi.spyOn(testApp.$registry, 'getAll').mockImplementation((registry) =>
    registry === 'element' ? { heading: type } : getAll(registry)
  )
  const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
  const wrapper = await testApp.mount(PickerHarness, {
    props: { page, placement },
    global: {
      provide: { builder, workspace: { id: 1 }, currentPage: page },
    },
  })
  if (open) {
    await wrapper.get('.open-picker').trigger('click')
    await flushPromises()
  }
  return { wrapper, dispatch, builder, page, sharedPage }
}

describe('AddElementModal', () => {
  test('checks element availability only while the picker is open', async () => {
    const isDisallowedReason = vi.fn(() => '')
    const { wrapper } = await openPicker({
      type: elementType({ isDisallowedReason }),
      open: false,
    })

    expect(isDisallowedReason).not.toHaveBeenCalled()
    expect(testApp.body.find('.item-picker-card').exists()).toBe(false)

    await wrapper.get('.open-picker').trigger('click')
    await flushPromises()
    expect(isDisallowedReason).toHaveBeenCalled()
    expect(testApp.body.get('.item-picker-card').text()).toContain('Heading')

    await testApp.body.get('.modal__close').trigger('click')
    await vi.waitFor(() => {
      expect(testApp.body.find('.item-picker-modal').exists()).toBe(false)
    })
    isDisallowedReason.mockClear()
    await wrapper.setProps({ placement: { pagePlace: PAGE_PLACES.HEADER } })
    expect(isDisallowedReason).not.toHaveBeenCalled()

    await wrapper.get('.open-picker').trigger('click')
    await flushPromises()
    expect(isDisallowedReason).toHaveBeenCalledWith(
      expect.objectContaining({ pagePlace: PAGE_PLACES.HEADER })
    )
    expect(testApp.body.get('.item-picker-card').text()).toContain('Heading')
  })

  test.each([
    [
      'at the page root',
      {},
      { referenceElementId: null, position: 'south', placeInContainer: '' },
    ],
    [
      'in an empty container slot',
      { parentElementId: 200, placeInContainer: '0' },
      { referenceElementId: 200, position: 'child', placeInContainer: '0' },
    ],
    [
      'before an element in a container',
      { parentElementId: 200, beforeId: 201, placeInContainer: '1' },
      { referenceElementId: 201, position: 'north', placeInContainer: '' },
    ],
    [
      'after a shared header',
      { afterId: 301 },
      { referenceElementId: 100, position: 'north', placeInContainer: '' },
    ],
  ])(
    'preserves insertion %s when selecting a card',
    async (_label, placement, expected) => {
      const { wrapper, dispatch, builder, page } = await openPicker({
        placement,
      })

      await testApp.body.get('.item-picker-card').trigger('click')
      await flushPromises()

      expect(dispatch).toHaveBeenCalledWith('element/create', {
        builder,
        page,
        elementType: 'heading',
        values: {},
        ...expected,
      })
      expect(
        wrapper.findComponent(AddElementModal).emitted('element-added')
      ).toHaveLength(1)
      await vi.waitFor(() => {
        expect(testApp.body.find('.item-picker-card').exists()).toBe(false)
      })
    }
  )

  test('creates header elements on the shared page', async () => {
    const { dispatch, sharedPage } = await openPicker({
      type: elementType({ pagePlace: PAGE_PLACES.HEADER }),
    })

    await testApp.body.get('.item-picker-card').trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith(
      'element/create',
      expect.objectContaining({
        page: sharedPage,
        referenceElementId: null,
        position: 'south',
      })
    )
  })

  test('keeps an unavailable category collapsed and blocks unavailable elements', async () => {
    const { dispatch } = await openPicker({
      type: elementType({
        isDisallowedReason: () => 'Not allowed in this container',
      }),
    })

    expect(testApp.body.find('.item-picker-card').exists()).toBe(false)
    const category = testApp.body
      .findAll('button')
      .find((button) => button.text() === 'addElementCategory.baseElement')
    await category.trigger('click')
    const card = testApp.body.get('.item-picker-card')
    expect(card.attributes('aria-disabled')).toBe('true')
    await card.trigger('click')

    expect(dispatch).not.toHaveBeenCalledWith(
      'element/create',
      expect.anything()
    )
  })
})
