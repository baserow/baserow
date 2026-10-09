import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, vi } from 'vitest'

import TemplateModalSwitch from '@baserow/modules/core/components/template/legacy/TemplateModalSwitch'

describe('TemplateModalSwitch', () => {
  const show = vi.fn()
  const hide = vi.fn()
  const modalStub = (name) =>
    defineComponent({
      name,
      props: ['workspace'],
      methods: { show, hide },
      template: `<div class="${name}" />`,
    })

  const mountComponent = (enabled) =>
    mountSuspended(TemplateModalSwitch, {
      props: { workspace: { id: 1 } },
      global: {
        mocks: {
          $featureFlagIsEnabled: (flag) => enabled && flag === 'user_templates',
        },
        stubs: {
          TemplateModal: modalStub('TemplateModal'),
          LegacyTemplateModal: modalStub('LegacyTemplateModal'),
        },
      },
    })

  it.each([
    [true, 'TemplateModal', 'LegacyTemplateModal'],
    [false, 'LegacyTemplateModal', 'TemplateModal'],
  ])(
    'with the flag %s renders %s and forwards show and hide',
    async (enabled, shown, hidden) => {
      show.mockClear()
      hide.mockClear()
      const wrapper = await mountComponent(enabled)

      expect(wrapper.find(`.${shown}`).exists()).toBe(true)
      expect(wrapper.find(`.${hidden}`).exists()).toBe(false)
      expect(wrapper.findComponent({ name: shown }).props('workspace')).toEqual(
        { id: 1 }
      )

      wrapper.vm.show('project-tracker')
      wrapper.vm.hide()
      expect(show).toHaveBeenCalledWith('project-tracker')
      expect(hide).toHaveBeenCalledTimes(1)
    }
  )
})
