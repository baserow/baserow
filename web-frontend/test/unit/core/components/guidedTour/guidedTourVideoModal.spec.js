import GuidedTourVideoModal from '@baserow/modules/core/components/guidedTour/GuidedTourVideoModal'
import { TestApp } from '@baserow/test/helpers/testApp'

const player = {
  loadVideoById: vi.fn(),
  destroy: vi.fn(),
}
let endVideo = null

vi.mock('@baserow/modules/core/utils/youtube', async (importOriginal) => ({
  ...(await importOriginal()),
  createYouTubePlayer: vi.fn((element, videoId, onEnded) => {
    endVideo = onEnded
    return Promise.resolve(player)
  }),
}))

describe('GuidedTourVideoModal component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    player.loadVideoById.mockClear()
    player.destroy.mockClear()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountAndShow = async (videos) => {
    const wrapper = await testApp.mount(GuidedTourVideoModal, {
      props: { videos },
    })
    await wrapper.vm.show(0)
    await wrapper.vm.$nextTick()
    return wrapper
  }

  const thumbnails = (wrapper) =>
    wrapper.findAll('.guided-tour-video-modal__thumbnail')

  test('no navigation is shown with a single video', async () => {
    const wrapper = await mountAndShow(['abc'])
    expect(wrapper.find('.guided-tour-video-modal__nav').exists()).toBe(false)
    expect(thumbnails(wrapper).length).toBe(0)
  })

  test('the next button plays the next video', async () => {
    const wrapper = await mountAndShow(['abc', 'def'])

    await wrapper.find('.guided-tour-video-modal__nav--next').trigger('click')

    expect(player.loadVideoById).toHaveBeenCalledWith('def')
    expect(
      thumbnails(wrapper)[1].classes(
        'guided-tour-video-modal__thumbnail--active'
      )
    ).toBe(true)
  })

  test('the navigation does not wrap around', async () => {
    const wrapper = await mountAndShow(['abc', 'def'])

    expect(
      wrapper
        .find('.guided-tour-video-modal__nav--previous')
        .classes('guided-tour-video-modal__nav--disabled')
    ).toBe(true)

    await wrapper.find('.guided-tour-video-modal__nav--next').trigger('click')

    expect(
      wrapper
        .find('.guided-tour-video-modal__nav--next')
        .classes('guided-tour-video-modal__nav--disabled')
    ).toBe(true)
  })

  test('a finished video automatically starts the next one', async () => {
    const wrapper = await mountAndShow(['abc', 'def'])

    endVideo()
    await wrapper.vm.$nextTick()

    expect(player.loadVideoById).toHaveBeenCalledWith('def')

    // The last video must not restart the first one.
    endVideo()
    expect(player.loadVideoById).toHaveBeenCalledTimes(1)
  })

  test('closing destroys the player so the video stops playing', async () => {
    const wrapper = await mountAndShow(['abc'])

    await wrapper.find('.guided-tour-video-modal__close').trigger('click')

    expect(player.destroy).toHaveBeenCalled()
  })

  // The modal must only hide on `click` because hiding on `mousedown` makes the
  // browser select the text of the page below.
  const clickOn = async (wrapper, selector) => {
    const element = wrapper.find(selector)
    await element.trigger('mousedown')
    await element.trigger('click')
  }

  test('clicking next to the video closes the modal', async () => {
    const wrapper = await mountAndShow(['abc'])

    await clickOn(wrapper, '.guided-tour-video-modal__body')

    expect(player.destroy).toHaveBeenCalled()
  })

  test('clicks do not reach the page, keeping open context menus open', async () => {
    const wrapper = await mountAndShow(['abc', 'def'])
    const onBodyClick = vi.fn()
    document.body.addEventListener('click', onBodyClick)

    await clickOn(wrapper, '.guided-tour-video-modal__close')
    await clickOn(wrapper, '.guided-tour-video-modal__nav--next')
    await clickOn(wrapper, '.guided-tour-video-modal__body')

    document.body.removeEventListener('click', onBodyClick)
    expect(onBodyClick).not.toHaveBeenCalled()
  })

  test('clicking the video or a button does not close the modal', async () => {
    const wrapper = await mountAndShow(['abc', 'def'])

    await clickOn(wrapper, '.guided-tour-video-modal__player')
    await clickOn(wrapper, '.guided-tour-video-modal__nav--next')

    expect(player.destroy).not.toHaveBeenCalled()
  })
})
