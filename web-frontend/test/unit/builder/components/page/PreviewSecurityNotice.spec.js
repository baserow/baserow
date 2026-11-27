import { mountSuspended } from '@nuxt/test-utils/runtime'
import PreviewSecurityNotice from '@baserow/modules/builder/components/page/PreviewSecurityNotice'

describe('PreviewSecurityNotice', () => {
  test('shows a short sentence and expands to the details and documentation', async () => {
    const wrapper = await mountSuspended(PreviewSecurityNotice)
    const toggle = wrapper.get('button')

    expect(wrapper.text()).toContain('previewSecurityNotice.summary')
    expect(wrapper.text()).not.toContain('previewSecurityNotice.details')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.attributes('aria-label')).toBe('previewSecurityNotice.expand')

    await toggle.trigger('click')

    expect(wrapper.text()).toContain('previewSecurityNotice.details')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(toggle.attributes('aria-label')).toBe(
      'previewSecurityNotice.collapse'
    )
    const link = wrapper.get('a')
    expect(link.text()).toBe('previewSecurityNotice.learnMore')
    expect(link.attributes('href')).toContain('baserow.io/docs/')
    expect(link.attributes('rel')).toBe('noopener noreferrer')

    await toggle.trigger('click')

    expect(wrapper.text()).not.toContain('previewSecurityNotice.details')
  })

  test('explains how to review untrusted content without linking to domain configuration', async () => {
    const wrapper = await mountSuspended(PreviewSecurityNotice, {
      props: { untrustedContent: true },
    })
    expect(wrapper.text()).toContain('previewSecurityNotice.untrustedSummary')
    await wrapper.get('button').trigger('click')
    expect(wrapper.text()).toContain('previewSecurityNotice.untrustedDetails')
    expect(wrapper.find('a').exists()).toBe(false)
    wrapper.unmount()
  })

  test('tells the page its height while shown, so a fixed header sits below it', async () => {
    const variable = '--preview-security-notice-height'
    const style = document.documentElement.style
    const wrapper = await mountSuspended(PreviewSecurityNotice)

    expect(style.getPropertyValue(variable)).toMatch(/^\d+px$/)

    wrapper.unmount()

    expect(style.getPropertyValue(variable)).toBe('')
  })
})
