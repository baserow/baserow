import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import SampleDataModal from '@baserow/modules/core/components/SampleDataModal'

const ModalStub = defineComponent({
  name: 'Modal',
  methods: {
    show() {},
    hide() {},
  },
  template: '<div class="modal-stub"><slot /></div>',
})

const ButtonStub = defineComponent({
  name: 'Button',
  inheritAttrs: false,
  template: '<button class="button-stub" v-bind="$attrs"><slot /></button>',
})

const TabsStub = defineComponent({
  name: 'Tabs',
  inheritAttrs: false,
  template: '<div class="tabs-stub"><slot /></div>',
})

const TabStub = defineComponent({
  name: 'Tab',
  props: { title: { type: String, required: false, default: '' } },
  template: '<div class="tab-stub" :data-title="title"><slot /></div>',
})

async function mountComponent(props = {}) {
  return await mountSuspended(SampleDataModal, {
    props: {
      sampleData: { subject: 'Hello' },
      title: 'Payload for trigger',
      subtitle: 'JSON payload',
      ...props,
    },
    global: {
      stubs: {
        Modal: ModalStub,
        Button: ButtonStub,
        Tabs: TabsStub,
        Tab: TabStub,
      },
      mocks: {
        $t: (key) => key,
      },
    },
  })
}

describe('SampleDataModal', () => {
  test('renders only the JSON payload by default', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.find('.tabs-stub').exists()).toBe(false)
    expect(wrapper.find('.sample-data-modal__code').text()).toContain(
      '"subject": "Hello"'
    )
  })

  test('renders JSON and HTML tabs for the html content type', async () => {
    const wrapper = await mountComponent({
      contentType: 'html',
      sampleDataHtml: '<p>An email body</p>',
    })

    expect(wrapper.find('.tabs-stub').exists()).toBe(true)
    const tabTitles = wrapper
      .findAll('.tab-stub')
      .map((tab) => tab.attributes('data-title'))
    expect(tabTitles).toStrictEqual(['JSON', 'HTML'])
    expect(wrapper.find('.sample-data-modal__code').text()).toContain(
      '"subject": "Hello"'
    )

    const iframe = wrapper.find('iframe.sample-data-modal__html-preview')
    expect(iframe.exists()).toBe(true)
    expect(iframe.attributes('srcdoc')).toBe('<p>An email body</p>')
    expect(iframe.attributes('sandbox')).toBe('')
  })

  test('shows a notice in the HTML tab when there is no HTML body', async () => {
    const wrapper = await mountComponent({
      contentType: 'html',
      sampleDataHtml: null,
    })

    expect(
      wrapper.find('iframe.sample-data-modal__html-preview').exists()
    ).toBe(false)
    expect(wrapper.text()).toContain('sampleDataViewer.noHtmlContent')
  })
})
