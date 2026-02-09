import Error from '@baserow/modules/core/components/Error'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Error Component Tests', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = (
    props = {
      error: {
        visible: true,
        title: 'error title',
        message: 'error content message',
      },
    }
  ) => {
    return testApp.mount(Error, { props })
  }

  test('When visible prop is true title and message are shown', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.html()).toContain('error title')
    expect(wrapper.find('.alert__message p').text()).toContain(
      'error content message'
    )
  })

  test('When visible prop is false no html is rendered', async () => {
    const wrapper = await mountComponent({ error: { visible: false } })

    expect(wrapper.text()).toStrictEqual('')
  })
})
