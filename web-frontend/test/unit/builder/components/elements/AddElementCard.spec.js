import { TestApp } from '@baserow/test/helpers/testApp'
import AddElementCard from '@baserow/modules/builder/components/elements/AddElementCard'

const UpgradeModal = {
  props: ['workspace', 'name'],
  data: () => ({ open: false }),
  methods: {
    show() {
      this.open = true
    },
  },
  template:
    '<div v-if="open" class="upgrade-modal">Upgrade to add {{ name }}</div>',
}

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(async () => {
  await testApp.afterEach()
})

describe('AddElementCard', () => {
  test('opens the upgrade flow for a licensed element without selecting it', async () => {
    const wrapper = await testApp.mount(AddElementCard, {
      props: {
        workspace: { id: 1 },
        builder: { id: 2 },
        page: { id: 3 },
        elementType: {
          name: 'Premium chart',
          description: 'Display a chart',
          image: '',
          isDisallowedReason: () => 'Upgrade required',
          getDeactivatedClickModal: () => [UpgradeModal, {}],
        },
      },
    })

    expect(wrapper.attributes('aria-disabled')).toBe('true')
    await wrapper.trigger('click')

    expect(wrapper.get('.upgrade-modal').text()).toBe(
      'Upgrade to add Premium chart'
    )
    expect(wrapper.emitted('click')).toBeUndefined()
  })
})
