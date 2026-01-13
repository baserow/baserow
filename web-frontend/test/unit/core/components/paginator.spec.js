import Paginator from '@baserow/modules/core/components/Paginator.vue'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Paginator.vue', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
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
