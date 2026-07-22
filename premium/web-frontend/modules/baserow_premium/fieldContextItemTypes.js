import { defineAsyncComponent, hydrateOnIdle } from 'vue'
import { Registerable } from '@baserow/modules/core/registry'

const GenerateAIValuesContextItem = defineAsyncComponent({
  loader: () =>
    import('@baserow_premium/components/field/GenerateAIValuesContextItem'),
  hydrate: hydrateOnIdle(),
})

export class GenerateAIValuesContextItemType extends Registerable {
  static getType() {
    return 'generate_ai_values'
  }

  getComponent() {
    return GenerateAIValuesContextItem
  }
}
