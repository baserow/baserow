import { Registerable } from '@baserow/modules/core/registry'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const GenerateAIValuesContextItem = lazyComponent(
  () => import('@baserow_premium/components/field/GenerateAIValuesContextItem')
)

export class GenerateAIValuesContextItemType extends Registerable {
  static getType() {
    return 'generate_ai_values'
  }

  getComponent() {
    return GenerateAIValuesContextItem
  }
}
