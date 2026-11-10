import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount } from '@vue/test-utils'
import HTMLElementForm from '@baserow_enterprise/builder/components/elements/HTMLElementForm'

enableAutoUnmount(afterEach)

function mountForm(html = '') {
  return mountSuspended(HTMLElementForm, {
    props: { defaultValues: { html } },
    global: {
      provide: {
        workspace: {},
        builder: { theme: {} },
        currentPage: {},
        elementPage: {},
        mode: 'editing',
      },
    },
  })
}

describe('HTML source form', () => {
  test.each([
    '<script>alert(1)</script>',
    '<ScRiPt src="https://example.com/widget.js"></ScRiPt>',
    '<template><script>alert(1)</script></template>',
    '<iframe srcdoc="&lt;script>alert(1)&lt;/script>"></iframe>',
    '<div onclick="alert(1)">Click</div>',
    '<a href="javascript:alert(1)">Link</a>',
  ])('immediately flags executable HTML: %s', async (html) => {
    const wrapper = await mountForm()
    const source = wrapper.get('textarea')

    await source.setValue(html)

    expect(source.attributes('aria-invalid')).toBe('true')
    expect(wrapper.get('[role="alert"]').text()).toBe('htmlElement.invalid')

    await source.setValue('<div class="widget" data-id="demo"></div>')

    expect(source.attributes('aria-invalid')).toBe('false')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  test('accepts empty source and escaped script examples', async () => {
    const wrapper = await mountForm()
    const source = wrapper.get('textarea')
    expect(source.attributes('aria-invalid')).toBe('false')

    await source.setValue('<code>&lt;script&gt;example&lt;/script&gt;</code>')

    expect(source.attributes('aria-invalid')).toBe('false')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })
})
