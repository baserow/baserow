import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import UntrustedContentReviewModal from '@baserow/modules/core/components/application/UntrustedContentReviewModal'

const report = [
  { type: 'iframe', id: 10, page_name: 'Home <script>bad()</script>' },
  { type: 'automation_code_node', id: 20, label: 'Transform data' },
  { type: 'external_script', id: 30, url: 'https://example.com/a.js' },
]

async function mountModal(overrides = {}) {
  const wrapper = await mountSuspended(UntrustedContentReviewModal, {
    props: {
      report,
      canTrust: true,
      trustContent: vi.fn().mockResolvedValue(undefined),
      ...overrides,
    },
    global: { stubs: { teleport: true } },
  })
  wrapper.vm.show()
  await nextTick()
  return wrapper
}

function trustButton(wrapper) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((button) => button.text() === 'untrustedContentReviewModal.trust')
}

test('shows the import snapshot and enables content only after confirmation', async () => {
  const trustContent = vi.fn().mockResolvedValue(undefined)
  const wrapper = await mountModal({ trustContent })
  expect(wrapper.find('.untrusted-content-report').html()).toMatchSnapshot()
  expect(wrapper.find('script').exists()).toBe(false)
  expect(trustContent).not.toHaveBeenCalled()
  await trustButton(wrapper).trigger('click')
  await flushPromises()
  expect(trustContent).toHaveBeenCalledOnce()
  wrapper.unmount()
})

test('keeps the report open and reports a failed trust update', async () => {
  const wrapper = await mountModal({
    trustContent: vi.fn().mockRejectedValue(new Error('denied')),
  })
  await trustButton(wrapper).trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('untrustedContentReviewModal.errorMessage')
  expect(wrapper.findComponent({ name: 'Modal' }).vm.isOpen()).toBe(true)
  wrapper.unmount()
})

test('read-only viewers can review the report without a trust control', async () => {
  const trustContent = vi.fn()
  const wrapper = await mountModal({ canTrust: false, trustContent })
  expect(wrapper.find('.untrusted-content-report').exists()).toBe(true)
  expect(trustButton(wrapper)).toBeUndefined()
  expect(trustContent).not.toHaveBeenCalled()
  wrapper.unmount()
})

test('explains when no import report is available', async () => {
  const wrapper = await mountModal({ report: [] })
  expect(wrapper.text()).toContain('untrustedContentReviewModal.empty')
  wrapper.unmount()
})
