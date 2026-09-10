import { defineComponent } from 'vue'

import AIFormulaModal from '@baserow_premium/components/field/AIFormulaModal'
import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'

const ModalStub = defineComponent({
  template: '<div><slot name="content" /></div>',
})

describe('AIFormulaModal model availability', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each([
    {
      name: 'eligible models',
      aiFeatures: { ai_fields: { models: { openai: ['gpt-4'] } } },
      available: true,
    },
    {
      name: 'an explicit empty allowlist',
      aiFeatures: { ai_fields: { models: {} } },
      available: false,
    },
    {
      name: 'a legacy availability payload',
      aiFeatures: undefined,
      available: true,
    },
  ])(
    'handles $name without the retired flag',
    async ({ aiFeatures, available }) => {
      await testApp.store.dispatch('workspace/forceCreate', {
        id: 1,
        generative_ai_models_enabled: { openai: ['gpt-4'] },
        ai_features: aiFeatures,
      })
      const wrapper = await testApp.mount(AIFormulaModal, {
        props: {
          database: { id: 1, workspace: { id: 1 } },
          table: { id: 1 },
        },
        global: {
          mocks: { $featureFlagIsEnabled: () => false },
          stubs: { Modal: ModalStub, AIFormulaForm: true },
        },
      })

      expect(wrapper.text().includes('aiFormulaModal.description')).toBe(
        available
      )
      expect(wrapper.text().includes('aiFormulaModal.noModels')).toBe(
        !available
      )
    }
  )
})
