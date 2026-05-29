import { mountSuspended } from '@nuxt/test-utils/runtime'

import AuthCodeInput from '@baserow/modules/core/components/settings/twoFactorAuth/AuthCodeInput.vue'

describe('AuthCodeInput.vue', () => {
  async function mountAuthCodeInput() {
    return await mountSuspended(AuthCodeInput, {
      attachTo: document.body,
    })
  }

  afterEach(() => {
    document.body.innerHTML = ''
  })

  test('moves focus to the next input as soon as a digit is entered', async () => {
    const wrapper = await mountAuthCodeInput()
    const inputs = wrapper.findAll('input')

    inputs.at(0).element.value = '2'
    await inputs.at(0).trigger('input')

    expect(document.activeElement).toBe(inputs.at(1).element)
  })

  test('captures alternating digits entered through the focused input sequence', async () => {
    const wrapper = await mountAuthCodeInput()
    const inputs = wrapper.findAll('input')

    for (const digit of '212121') {
      const activeInput = inputs.find(
        (input) => input.element === document.activeElement
      )

      activeInput.element.value = digit
      await activeInput.trigger('input')
    }

    expect(inputs.map((input) => input.element.value).join('')).toBe('212121')
    expect(wrapper.emitted('all-filled')[0]).toEqual(['212121'])
  })
})
