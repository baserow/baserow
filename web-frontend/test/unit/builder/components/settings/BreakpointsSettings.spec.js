import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import BreakpointsSettings from '@baserow/modules/builder/components/settings/BreakpointsSettings'

describe('BreakpointsSettings', () => {
  let wrapper
  let dispatch

  const builder = {
    id: 1,
    mobile_breakpoint: 640,
    tablet_breakpoint: 1024,
  }

  const mountComponent = async () => {
    wrapper = await mountSuspended(BreakpointsSettings, {
      props: { builder },
      global: {
        mocks: {
          $store: { dispatch },
          $t: (key) => key,
        },
        stubs: {
          Button: {
            name: 'Button',
            props: ['disabled'],
            template: '<button :disabled="disabled"><slot /></button>',
          },
          Error: true,
          FormGroup: { template: '<div><slot /></div>' },
        },
      },
    })
  }

  beforeEach(async () => {
    dispatch = vi.fn().mockResolvedValue()
    await mountComponent()
  })

  afterEach(() => wrapper.unmount())

  test('disables save while the breakpoint values are invalid', async () => {
    const form = wrapper.findComponent({
      name: 'BuilderBreakpointsSettingsForm',
    })

    form.vm.v$.values.tablet_breakpoint.$model = 640
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.invalidForm).toBe(true)
    expect(wrapper.findComponent({ name: 'Button' }).props('disabled')).toBe(
      true
    )
  })

  test('prevents duplicate breakpoint updates', async () => {
    let resolveUpdate
    dispatch.mockImplementation(
      () => new Promise((resolve) => (resolveUpdate = resolve))
    )

    const values = { mobile_breakpoint: 700, tablet_breakpoint: 1100 }
    const firstUpdate = wrapper.vm.updateBreakpoints(values)
    await wrapper.vm.updateBreakpoints(values)

    expect(dispatch).toHaveBeenCalledTimes(1)

    resolveUpdate()
    await firstUpdate
  })

  test('saves the values entered in the breakpoint inputs', async () => {
    const [mobileInput, tabletInput] = wrapper.findAll('input')

    await mobileInput.setValue('700')
    await tabletInput.setValue('1100')
    wrapper
      .findComponent({ name: 'BuilderBreakpointsSettingsForm' })
      .vm.submit()

    expect(dispatch).toHaveBeenCalledWith('application/update', {
      application: builder,
      values: { mobile_breakpoint: 700, tablet_breakpoint: 1100 },
    })
  })

  test('keeps the entered values after a server error', async () => {
    const form = wrapper.findComponent({
      name: 'BuilderBreakpointsSettingsForm',
    })
    form.vm.v$.values.mobile_breakpoint.$model = 700
    form.vm.v$.values.tablet_breakpoint.$model = 1100
    await wrapper.vm.$nextTick()

    dispatch.mockRejectedValue({
      handler: {
        getMessage: () => ({ title: 'Error', message: 'Could not save.' }),
        handled: vi.fn(),
      },
    })

    await wrapper.vm.updateBreakpoints({
      mobile_breakpoint: 700,
      tablet_breakpoint: 1100,
    })

    expect(form.vm.values).toEqual({
      mobile_breakpoint: 700,
      tablet_breakpoint: 1100,
    })
    expect(wrapper.vm.error.visible).toBe(true)
    expect(wrapper.vm.actionInProgress).toBe(false)
  })
})
