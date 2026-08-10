import GuidedTourStep from '@baserow/modules/core/components/guidedTour/GuidedTourStep'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('GuidedTourStep component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = ({ props = {} } = {}) => {
    return testApp.mount(GuidedTourStep, {
      props: {
        position: 'center',
        step: 1,
        totalSteps: 2,
        title: 'Title',
        content: 'Content',
        ...props,
      },
    })
  }

  test('no video is shown if the step has none', async () => {
    const wrapper = await mountComponent()
    expect(wrapper.find('.guided-tour-step__video').exists()).toBe(false)
  })

  test('the thumbnail of the first video is shown', async () => {
    const wrapper = await mountComponent({
      props: { videos: ['abc', 'def'] },
    })
    expect(
      wrapper.find('.guided-tour-step__video-thumbnail img').attributes().src
    ).toBe('https://img.youtube.com/vi/abc/mqdefault.jpg')
    expect(wrapper.find('.guided-tour-step__academy').attributes().href).toBe(
      'https://academy.baserow.io/'
    )
  })

  test('the video is hidden if the thumbnail can not be loaded', async () => {
    const wrapper = await mountComponent({ props: { videos: ['abc'] } })

    await wrapper
      .find('.guided-tour-step__video-thumbnail img')
      .trigger('error')

    expect(wrapper.find('.guided-tour-step__video').exists()).toBe(false)
  })

  test('the video is shown again after moving to another step', async () => {
    const wrapper = await mountComponent({ props: { videos: ['abc'] } })

    await wrapper
      .find('.guided-tour-step__video-thumbnail img')
      .trigger('error')
    await wrapper.setProps({ videos: ['def'] })

    expect(
      wrapper.find('.guided-tour-step__video-thumbnail img').attributes().src
    ).toBe('https://img.youtube.com/vi/def/mqdefault.jpg')
  })

  test('the thumbnail is hidden until it has loaded', async () => {
    const wrapper = await mountComponent({ props: { videos: ['abc'] } })
    const image = () => wrapper.find('.guided-tour-step__video-thumbnail img')
    const isVisible = () => image().element.style.display !== 'none'

    expect(isVisible()).toBe(false)
    expect(wrapper.find('.guided-tour-step__video-loading').exists()).toBe(true)

    await image().trigger('load')

    expect(isVisible()).toBe(true)
    expect(wrapper.find('.guided-tour-step__video-loading').exists()).toBe(
      false
    )
  })

  test('the thumbnail of the previous step is not shown while loading', async () => {
    const wrapper = await mountComponent({ props: { videos: ['abc'] } })
    await wrapper.find('.guided-tour-step__video-thumbnail img').trigger('load')

    await wrapper.setProps({ videos: ['def'] })

    const image = wrapper.find('.guided-tour-step__video-thumbnail img')
    expect(image.element.style.display).toBe('none')
    expect(wrapper.find('.guided-tour-step__video-loading').exists()).toBe(true)
  })

  test('the thumbnail stays visible when the step is rendered again', async () => {
    const wrapper = await mountComponent({ props: { videos: ['abc'] } })
    await wrapper.find('.guided-tour-step__video-thumbnail img').trigger('load')

    // The step getters build a new array on every render, so the same videos arrive
    // as a new instance. That must not put the thumbnail back into loading state
    // because the image element is not replaced and would never load again.
    await wrapper.setProps({ videos: ['abc'] })

    const image = wrapper.find('.guided-tour-step__video-thumbnail img')
    expect(image.element.style.display).not.toBe('none')
    expect(wrapper.find('.guided-tour-step__video-loading').exists()).toBe(
      false
    )
  })
})
