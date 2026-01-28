import { TestApp } from '@baserow/test/helpers/testApp'
import PreviewAny from '@baserow/modules/database/components/preview/PreviewAny'

describe('Preview component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = (props = { mimeType: '', url: '' }, slots = {}) => {
    return testApp.mount(PreviewAny, { propsData: props, slots })
  }

  test('Default preview component', async () => {
    const wrapper = await mountComponent()
    expect(wrapper.element).toMatchSnapshot()
  })

  test('Preview component with default', async () => {
    const wrapper = await mountComponent(undefined, {
      fallback: '<div class="default"/>',
    })
    expect(wrapper.element).toMatchSnapshot()
  })

  test('Image preview component', async () => {
    const wrapper = await mountComponent({
      mimeType: 'image/png',
      url: 'https://baserow.io/logo.png',
    })
    expect(wrapper.element).toMatchSnapshot()
  })

  test('Video preview component', async () => {
    const wrapper = await mountComponent(
      {
        mimeType: 'video/mp4',
        url: 'https://baserow.io/video.mpg',
      },
      {
        fallback: '<div class="default"/>',
      }
    )
    expect(wrapper.element).toMatchSnapshot()
  })

  test('Audio preview component', async () => {
    const wrapper = await mountComponent(
      {
        mimeType: 'audio/mpeg',
        url: 'https://baserow.io/audio.mp3',
      },
      {
        fallback: '<div class="default"/>',
      }
    )
    expect(wrapper.element).toMatchSnapshot()
  })

  test('PDF preview component', async () => {
    const wrapper = await mountComponent(
      {
        mimeType: 'application/pdf',
        url: 'https://baserow.io/file.pdf',
      },
      {
        fallback: '<div class="default"/>',
      }
    )
    expect(wrapper.element).toMatchSnapshot()

    const button = wrapper.find('.preview__select-buttons button:first-child')
    await button.trigger('click')

    expect(wrapper.element).toMatchSnapshot()

    // Test updating url reset the choice
    await wrapper.setProps({
      mimeType: 'application/pdf',
      url: 'https://baserow.io/file2.pdf',
    })

    expect(wrapper.element).toMatchSnapshot()

    const button2 = wrapper.find('.preview__select-buttons button:last-child')
    await button2.trigger('click')

    expect(wrapper.element).toMatchSnapshot()
  })

  test('Office preview', async () => {
    const wrapper = await mountComponent(
      {
        mimeType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        url: 'https://baserow.iapplication/vnd.openxmlformats-officedocument.wordprocessingml.documento/file.xlsx',
      },
      {
        fallback: '<div class="default"/>',
      }
    )
    expect(wrapper.element).toMatchSnapshot()

    const button = wrapper.find('.preview__select-buttons button:first-child')
    await button.trigger('click')

    expect(wrapper.element).toMatchSnapshot()
  })
})
