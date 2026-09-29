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
          Checkbox: { template: '<label><slot /></label>' },
        },
      },
    })
  }

  test('persists the same-origin permission only for URL sources', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.vm.allowedValues).toEqual([
      'source_type',
      'url',
      'embed',
      'height',
      'allow_same_origin',
      'styles',
    ])
    expect(wrapper.vm.values.allow_same_origin).toBe(true)
    expect(wrapper.text()).toContain('iframeElementForm.allowSameOriginLabel')

    await wrapper.setData({
      values: {
        ...wrapper.vm.values,
        source_type: IFRAME_SOURCE_TYPES.EMBED,
      },
    })

    expect(wrapper.text()).not.toContain(
      'iframeElementForm.allowSameOriginLabel'
    )
  })
})
