import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import BuilderBreakpointsSettingsForm from '@baserow/modules/builder/components/form/BuilderBreakpointsSettingsForm'
import {
  MAX_BUILDER_BREAKPOINT,
  MIN_BUILDER_BREAKPOINT,
} from '@baserow/modules/builder/utils/breakpoints'

describe('BuilderBreakpointsSettingsForm', () => {
  let wrapper

  beforeEach(async () => {
    wrapper = await mountSuspended(BuilderBreakpointsSettingsForm, {
      props: {
        defaultValues: {
          breakpoints: { mobile: 640, tablet: 1024, laptop: 1280 },
        },
      },
      global: {
        mocks: {
          $t: (key) => key,
        },
        stubs: {
          FormGroup: {
            props: ['errorMessage'],
            template:
              '<div class="form-group-stub"><slot name="label" /><span v-if="errorMessage" class="form-group-stub__error">{{ errorMessage }}</span><slot /></div>',
          },
        },
      },
    })
  })

  afterEach(() => wrapper.unmount())

  test('submits valid breakpoint values', () => {
    wrapper.vm.submit()

    expect(wrapper.emitted('submitted')).toEqual([
      [{ breakpoints: { mobile: 640, tablet: 1024, laptop: 1280 } }],
    ])
  })

  test('submits values entered in the breakpoint inputs', async () => {
    const inputs = wrapper.findAll('input')
    const [mobileInput, tabletInput] = inputs

    expect(inputs).toHaveLength(2)

    await mobileInput.setValue('700')
    await tabletInput.setValue('1100')
    wrapper.vm.submit()

    expect(wrapper.emitted('submitted')).toEqual([
      [{ breakpoints: { mobile: 700, tablet: 1100, laptop: 1280 } }],
    ])
  })

  test('uses compact inputs for breakpoint values', () => {
    expect(
      wrapper.findAll('.builder-breakpoints-settings-form__input')
    ).toHaveLength(2)
  })

  test('limits inputs to supported breakpoint values', () => {
    const [mobileInput, tabletInput] = wrapper.findAll('input')

    for (const input of [mobileInput, tabletInput]) {
      expect(input.attributes('min')).toBe(String(MIN_BUILDER_BREAKPOINT))
      expect(input.attributes('max')).toBe(String(MAX_BUILDER_BREAKPOINT))
      expect(input.attributes('step')).toBe('1')
    }
  })

  test('explains how breakpoint changes affect the application', () => {
    expect(
      wrapper.find('.builder-breakpoints-settings-form__description').text()
    ).toBe('breakpointSettings.description')
  })

  test('shows the matching device icon in each breakpoint label', () => {
    expect(
      wrapper.findAll('.builder-breakpoints-settings-form__label-icon')
    ).toHaveLength(3)
    expect(wrapper.find('.baserow-icon-smartphone').exists()).toBe(true)
    expect(wrapper.find('.baserow-icon-tablet').exists()).toBe(true)
    expect(wrapper.find('.iconoir-apple-imac-2021').exists()).toBe(true)
  })

  test('shows desktop as a read-only breakpoint', () => {
    expect(
      wrapper.find('.builder-breakpoints-settings-form__desktop-value').text()
    ).toBe('breakpointSettings.desktopDescription')
  })

  test('rejects a tablet breakpoint that is not greater than mobile', async () => {
    const [, tabletInput] = wrapper.findAll('input')

    await tabletInput.setValue('640')

    wrapper.vm.submit()

    expect(
      wrapper
        .findAll('.form-group-stub')
        .at(1)
        .find('.form-group-stub__error')
        .text()
    ).toBe('breakpointSettings.tabletMustBeGreaterThanMobile')
    expect(wrapper.emitted('submitted')).toBeUndefined()
  })

  test.each([
    ['mobile', MIN_BUILDER_BREAKPOINT - 1, 'error.minValueField'],
    ['mobile', MAX_BUILDER_BREAKPOINT + 1, 'error.maxValueField'],
    ['tablet', MIN_BUILDER_BREAKPOINT - 1, 'error.minValueField'],
    ['tablet', MAX_BUILDER_BREAKPOINT + 1, 'error.maxValueField'],
  ])(
    'shows the %s bound validation error for an out-of-range breakpoint',
    async (breakpoint, value, expectedError) => {
      const inputIndex = breakpoint === 'mobile' ? 0 : 1
      const formGroup = wrapper.findAll('.form-group-stub').at(inputIndex)

      await wrapper.findAll('input').at(inputIndex).setValue(String(value))

      wrapper.vm.submit()

      expect(formGroup.find('.form-group-stub__error').text()).toBe(
        expectedError
      )
      expect(wrapper.emitted('submitted')).toBeUndefined()
    }
  )
})
