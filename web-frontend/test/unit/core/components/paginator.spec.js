import Paginator from '@baserow/modules/core/components/Paginator.vue'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Paginator.vue', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = ({
    props = { totalPages: 5, page: 1 },
    listeners = {},
    slots = {},
  } = {}) => {
    return testApp.mount(Paginator, { propsData: props, listeners, slots })
  }

  it('renders paginator correctly', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.find('.paginator__content-input').element.value).toBe('1')
    expect(wrapper.find('.paginator__button--disabled').exists()).toBe(true)
  })

  it('accepts a page on Enter and does not submit it again on blur', async () => {
    const wrapper = await mountComponent()
    const input = wrapper.get('input')
    input.element.value = '3'
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('change-page')).toEqual([[3]])
    await wrapper.setProps({ page: 3 })
    await input.trigger('change')
    expect(wrapper.emitted('change-page')).toEqual([[3]])
  })

  it.each(['0', '6', '', 'abc', '2abc', '2.5'])(
    'restores the current page for invalid input %s',
    async (value) => {
      const wrapper = await mountComponent()
      await wrapper.get('input').setValue(value)
      expect(wrapper.emitted('change-page')).toBeFalsy()
      expect(wrapper.get('input').element.value).toBe('1')
    }
  )

  it('emits change-page event when next page button is clicked', async () => {
    const wrapper = await mountComponent()
    await wrapper.findAll('.paginator__button').at(1).trigger('click')

    expect(wrapper.emitted('change-page')).toBeTruthy()
    expect(wrapper.emitted('change-page')[0]).toEqual([2])
  })

  it('does not emit change-page event when previous page button is clicked and current page is the first page', async () => {
    const wrapper = await mountComponent()
    await wrapper.findAll('.paginator__button').at(0).trigger('click')

    expect(wrapper.emitted('change-page')).toBeFalsy()
  })
})
