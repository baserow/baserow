import ItemPickerCard from '@baserow/modules/core/components/ItemPickerCard'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('ItemPickerCard', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountCard(props = {}) {
    return testApp.mount(ItemPickerCard, {
      props: { name: 'Chart', image: '/chart.svg', ...props },
    })
  }

  test('emits selection for an available item', async () => {
    const wrapper = await mountCard()

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('click')).toHaveLength(1)
    expect(wrapper.get('button').attributes('type')).toBe('button')
    expect(wrapper.get('button').attributes('aria-label')).toBe('Chart')
  })

  test.each([{ disabled: true }, { loading: true }])(
    'blocks selection while disabled or loading: %s',
    async (props) => {
      const wrapper = await mountCard(props)

      await wrapper.get('button').trigger('click')

      expect(wrapper.get('button').element.disabled).toBe(true)
      expect(wrapper.emitted('click')).toBeUndefined()
      expect(wrapper.get('button').attributes('aria-disabled')).toBe('true')
    }
  )

  test('keeps unavailable items interactive for the owner to explain restrictions', async () => {
    const wrapper = await mountCard({ unavailable: true, locked: true })

    await wrapper.get('button').trigger('click')

    expect(wrapper.get('button').element.disabled).toBe(false)
    expect(wrapper.get('button').attributes('aria-disabled')).toBe('true')
    expect(wrapper.find('.item-picker-card__lock').exists()).toBe(true)
    expect(wrapper.emitted('click')).toHaveLength(1)
  })
})
