import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import BuilderBreakpointsSettingsForm from '@baserow/modules/builder/components/form/BuilderBreakpointsSettingsForm'

describe('BuilderBreakpointsSettingsForm', () => {
  let wrapper

  beforeEach(async () => {
    wrapper = await mountSuspended(BuilderBreakpointsSettingsForm, {
      props: {
        defaultValues: {
          mobile_breakpoint: 640,
          tablet_breakpoint: 1024,
        },
      },
      global: {
        mocks: {
          $t: (key) => key,
        },
        stubs: {
          FormGroup: { template: '<div><slot /></div>' },
          FormInput: { template: '<div><slot /></div>' },
        },
      },
    })
  })

  afterEach(() => wrapper.unmount())

  test('submits valid breakpoint values', () => {
    wrapper.vm.submit()

    expect(wrapper.emitted('submitted')).toEqual([
      [{ mobile_breakpoint: 640, tablet_breakpoint: 1024 }],
    ])
  })

  test('uses compact inputs for breakpoint values', () => {
    expect(
      wrapper.findAll('.builder-breakpoints-settings-form__input')
    ).toHaveLength(2)
  })

  test('rejects a tablet breakpoint that is not greater than mobile', async () => {
    wrapper.vm.v$.values.tablet_breakpoint.$model = 640
    await wrapper.vm.$nextTick()

    wrapper.vm.submit()

    expect(wrapper.vm.v$.values.tablet_breakpoint.$invalid).toBe(true)
    expect(wrapper.emitted('submitted')).toBeUndefined()
  })
})
