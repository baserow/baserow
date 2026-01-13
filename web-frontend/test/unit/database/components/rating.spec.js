import { TestApp } from '@baserow/test/helpers/testApp'
import Rating from '@baserow/modules/database/components/Rating'

describe('Rating component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = (
    props = { value: 3, maxValue: 5, readOnly: true },
    listeners = {}
  ) => {
    return testApp.mount(Rating, { propsData: props, listeners })
  }

  const changeValue = async (wrapper, value) => {
    const star = wrapper.find(`.rating :nth-child(${value})`)

    await star.trigger('click')
  }

  test('Default rating component', async () => {
    const wrapper = await mountComponent()
    expect(wrapper.element).toMatchSnapshot()
  })

  test('Customized rating component', async () => {
    const wrapper = await mountComponent({
      value: 3,
      maxValue: 5,
      readOnly: false,
      style: 'flag',
      color: 'dark-blue',
    })
    expect(wrapper.element).toMatchSnapshot()
  })

  test('interactions with rating component', async () => {
    const onUpdate = vi.fn()
    const wrapper = await mountComponent(
      {
        value: 3,
        maxValue: 5,
        readOnly: false,
      },
      { update: onUpdate }
    )

    changeValue(wrapper, 1)
    expect(onUpdate).toHaveBeenCalledWith(1)

    changeValue(wrapper, 5)
    expect(onUpdate).toHaveBeenCalledWith(5)

    // If we click on current value, should set value to 0
    changeValue(wrapper, 3)
    expect(onUpdate).toHaveBeenCalledWith(0)
  })
})
