import { mountSuspended } from '@nuxt/test-utils/runtime'
import { h } from 'vue'

import { IFRAME_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import IFrameElementForm from '@baserow/modules/builder/components/elements/components/forms/general/IFrameElementForm.vue'

describe('IFrameElementForm', () => {
  const mountComponent = (props = {}) => {
    return mountSuspended(IFrameElementForm, {
      props: {
        defaultValues: {
          source_type: IFRAME_SOURCE_TYPES.URL,
          url: { formula: '"https://example.com"' },
          embed: {},
          height: 300,
          allow_same_origin: true,
          styles: {},
          ...props.defaultValues,
        },
      },
      mocks: {
        $t: (key) => key,
        $registry: {
          getOrderedList: () => [],
        },
      },
      global: {
        provide: {
          workspace: {},
          builder: { theme: {} },
          currentPage: {},
          elementPage: {},
          mode: 'editing',
          formulaComponent: () => h('div', 'fake formula component'),
          dataProvidersAllowed: [],
        },
        stubs: {
          FormGroup: {
            props: ['label'],
            template: '<div>{{ label }}<slot /><slot name="helper" /></div>',
          },
          RadioGroup: true,
          Alert: true,
          InjectedFormulaInput: true,
          FormInput: true,
        },
      },
    })
  }

  test('shows the same-origin permission only for URL sources', async () => {
    const wrapper = await mountComponent()
    expect(wrapper.text()).toContain('iframeElementForm.allowSameOriginLabel')
    expect(wrapper.find('input[type="checkbox"]').element.checked).toBe(true)
    expect(wrapper.text()).not.toContain('iframeElementForm.autoHeightLabel')
    wrapper.unmount()
  })

  test('defaults automatic height to off and emits the changed option for embeds', async () => {
    const wrapper = await mountComponent({
      defaultValues: { source_type: IFRAME_SOURCE_TYPES.EMBED },
    })
    expect(wrapper.text()).not.toContain(
      'iframeElementForm.allowSameOriginLabel'
    )
    expect(wrapper.text()).toContain('iframeElementForm.autoHeightLabel')
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.element.checked).toBe(false)
    await checkbox.setValue(true)
    expect(wrapper.emitted('values-changed').at(-1)[0]).toMatchObject({
      auto_height: true,
    })
    await checkbox.setValue(false)
    expect(wrapper.emitted('values-changed').at(-1)[0]).toMatchObject({
      auto_height: false,
    })
    wrapper.unmount()
  })

  test('loads an existing automatic height setting', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        source_type: IFRAME_SOURCE_TYPES.EMBED,
        auto_height: true,
      },
    })
    expect(wrapper.find('input[type="checkbox"]').element.checked).toBe(true)
    wrapper.unmount()
  })
})
