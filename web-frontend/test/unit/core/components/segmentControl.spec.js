import { TestApp } from '@baserow/test/helpers/testApp'
import SegmentControl from '@baserow/modules/core/components/SegmentControl.vue'

describe('SegmentControl.vue', () => {
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
    return testApp.mount(SegmentControl, {
      propsData: {
        segments: [{ label: 'One' }, { label: 'Two' }, { label: 'Three' }],
        initialActiveIndex: 1,
      },
      listeners,
      slots,
    })
  }
  it('renders the correct number of segments', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.findAll('.segment-control__button').length).toBe(3)
  })

  it('sets the active segment correctly', async () => {
    const wrapper = await mountComponent()

    expect(
      wrapper.findAll('.segment-control__button--active').at(0).text()
    ).toBe('Two')
  })

  it('emits update:activeIndex event with the correct index when a segment is clicked', async () => {
    const wrapper = await mountComponent()
    await wrapper.findAll('.segment-control__button').at(2).trigger('click')

    expect(wrapper.emitted('update:activeIndex')[0]).toEqual([2])
  })
})
