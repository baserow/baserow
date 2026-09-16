import { mountSuspended } from '@nuxt/test-utils/runtime'
import ABFileInput from '@baserow/modules/builder/components/elements/baseComponents/ABFileInput.vue'

describe('ABFileInput image previews', () => {
  let wrapper

  afterEach(() => {
    wrapper?.unmount()
    vi.restoreAllMocks()
  })

  test.each([
    [true, undefined],
    [false, undefined],
    [true, false],
    [false, false],
  ])(
    'shows a selected image when previews are enabled (multiple=%s, preview=%s)',
    async (multiple, preview) => {
      const image = new File(['image contents'], 'photo.png', {
        type: 'image/png',
      })
      const previewUrl = 'blob:http://localhost/photo'
      const createObjectURL = vi
        .spyOn(URL, 'createObjectURL')
        .mockReturnValue(previewUrl)
      wrapper = await mountSuspended(ABFileInput, {
        props: { multiple, preview },
      })
      const input = wrapper.get('input[type="file"]')
      Object.defineProperty(input.element, 'files', { value: [image] })
      await input.trigger('change')

      expect(wrapper.get('.ab-presentation__title').text()).toBe('photo.png')
      if (preview === false) {
        expect(wrapper.find('img').exists()).toBe(false)
        expect(wrapper.find('.ab-avatar__icon').exists()).toBe(true)
        expect(createObjectURL).not.toHaveBeenCalled()

        await wrapper.setProps({ preview: true })
      }

      expect(wrapper.get('img').attributes('src')).toBe(previewUrl)
      expect(createObjectURL).toHaveBeenCalledWith(image)
      expect(wrapper.find('.ab-avatar__icon').exists()).toBe(false)
    }
  )
})
