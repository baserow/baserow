import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

describe('Grouped aggregation upgrade modal', () => {
  let testApp

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each([null, { id: 1 }])(
    'shows the Advanced plan with workspace %s',
    async (workspace) => {
      const wrapper = await testApp.mount(
        {
          components: { PaidFeaturesModal },
          props: ['workspace'],
          template: `
            <div>
              <button @click="$refs.upgrade.show()">Upgrade</button>
              <PaidFeaturesModal
                ref="upgrade"
                :workspace="workspace"
                initial-selected-type="builder_grouped_aggregate_rows"
              />
            </div>
          `,
        },
        {
          props: { workspace },
        }
      )

      await wrapper.find('button').trigger('click')

      expect(testApp.body.find('.box__title').text()).toBe(
        'premiumFeatures.groupedAggregateRowsDataSource'
      )
      expect(
        testApp.body
          .find('.modal-sidebar__nav-link.active')
          .element.parentElement.parentElement.previousElementSibling.textContent.trim()
      ).toBe('Advanced')
      expect(testApp.body.find('.modal__box-content > p').text()).toBe(
        'paidFeaturesModal.description'
      )
    }
  )
})
