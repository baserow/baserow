import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import BuilderBreakpointsSettingsForm from '@baserow/modules/builder/components/form/BuilderBreakpointsSettingsForm'

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
          FormGroup: { template: '<div><slot name="label" /><slot /></div>' },
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
    wrapper.vm.v$.values.breakpoints.tablet.$model = 640
    await wrapper.vm.$nextTick()

    wrapper.vm.submit()

    expect(wrapper.vm.v$.values.breakpoints.tablet.$invalid).toBe(true)
    expect(wrapper.emitted('submitted')).toBeUndefined()
  })
})
