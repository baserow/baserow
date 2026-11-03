import { flushPromises } from '@vue/test-utils'
import ItemPickerModal from '@baserow/modules/core/components/ItemPickerModal'
import { TestApp } from '@baserow/test/helpers/testApp'

const groups = [
  {
    id: 'content',
    label: 'Content',
    items: [
      { name: 'Heading', description: 'Display a title' },
      { name: 'Image', description: 'Display a picture' },
    ],
  },
  {
    id: 'form',
    label: 'Form',
    initiallyCollapsed: true,
    items: [{ name: 'Input', description: 'Collect an answer' }],
  },
  { id: 'empty', label: 'Empty', items: [] },
]

const PickerHarness = {
  components: { ItemPickerModal },
  props: ['groups'],
  template: `
    <div>
      <button class="open-picker" @click="$refs.picker.show()">Open</button>
      <button class="hide-picker" @click="$refs.picker.hide()">Hide</button>
      <button class="toggle-picker" @click="$refs.picker.toggle()">Toggle</button>
      <ItemPickerModal ref="picker" title="Add item" search-placeholder="Search items" :groups="groups">
        <template #items="{ items }">
          <button v-for="item in items" :key="item.name" class="picker-option">{{ item.name }}</button>
        </template>
      </ItemPickerModal>
    </div>
  `,
}

describe('ItemPickerModal', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function openPicker() {
    const wrapper = await testApp.mount(PickerHarness, {
      props: { groups },
      global: { stubs: { Teleport: false } },
    })
    await wrapper.get('.open-picker').trigger('click')
    return wrapper
  }

  test('focuses search and finds items by name or description in collapsed groups', async () => {
    await openPicker()

    const search = testApp.body.get('.item-picker-modal input')
    expect(document.activeElement).toBe(search.element)
    expect(
      testApp.body
        .findAll('.item-picker-modal__group-title')
        .map((group) => group.text())
    ).toEqual(['Content', 'Form'])
    expect(
      testApp.body.findAll('.picker-option').map((item) => item.text())
    ).toEqual(['Heading', 'Image'])

    await search.setValue(' ANSWER ')
    await flushPromises()
    expect(
      testApp.body.findAll('.picker-option').map((item) => item.text())
    ).toEqual(['Input'])
    expect(testApp.body.get('.item-picker-modal__group-title').text()).toBe(
      'Form'
    )

    await search.setValue('heading')
    await flushPromises()
    expect(document.activeElement).toBe(search.element)
    expect(
      testApp.body.findAll('.picker-option').map((item) => item.text())
    ).toEqual(['Heading'])

    await search.setValue('missing')
    await flushPromises()
    expect(testApp.body.find('.picker-option').exists()).toBe(false)
    expect(testApp.body.get('.item-picker-modal__empty').text()).toBe(
      'itemPickerModal.noResults'
    )
  })

  test('lets users collapse categories and temporarily reveals matches during search', async () => {
    await openPicker()

    const category = testApp.body.get('.item-picker-modal__group-title')
    await category.trigger('click')
    await flushPromises()
    expect(category.attributes('aria-expanded')).toBe('false')
    expect(testApp.body.find('.picker-option').exists()).toBe(false)

    const search = testApp.body.get('.item-picker-modal input')
    await search.setValue('heading')
    await flushPromises()
    expect(category.attributes('aria-expanded')).toBe('true')
    expect(testApp.body.get('.picker-option').text()).toBe('Heading')

    await search.setValue('')
    await flushPromises()
    expect(category.attributes('aria-expanded')).toBe('false')
    expect(testApp.body.find('.picker-option').exists()).toBe(false)
  })

  test('keeps search when hidden and reopened through the modal API', async () => {
    const wrapper = await openPicker()
    await testApp.body.get('.item-picker-modal input').setValue('picture')
    await wrapper.get('.hide-picker').trigger('click')
    await vi.waitFor(() => {
      expect(testApp.body.find('.item-picker-modal').exists()).toBe(false)
    })

    await wrapper.get('.toggle-picker').trigger('click')
    const search = testApp.body.get('.item-picker-modal input')
    expect(search.element.value).toBe('picture')
    expect(document.activeElement).toBe(search.element)
    expect(testApp.body.get('.picker-option').text()).toBe('Image')
  })
})
