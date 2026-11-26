import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import GenerateAIValuesJobListItem from '@baserow_premium/components/field/GenerateAIValuesJobListItem'

describe('GenerateAIValuesJobListItem component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('tells why a job failed', async () => {
    const wrapper = await testApp.mount(GenerateAIValuesJobListItem, {
      props: {
        field: { id: 1 },
        jobItem: {
          id: 1,
          state: 'failed',
          row_ids: [1],
          human_readable_error: 'No AI credits left.',
        },
      },
    })

    expect(wrapper.get('.generate-ai-values-job__error').text()).toBe(
      'No AI credits left.'
    )
  })
})
