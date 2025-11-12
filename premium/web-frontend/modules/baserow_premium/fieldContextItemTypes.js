import { Registerable } from '@baserow/modules/core/registry'
import GenerateAIValuesContextItem from '@baserow_premium/components/field/GenerateAIValuesContextItem'

export class GenerateAIValuesContextItemType extends Registerable {
  static getType() {
    return 'generate_ai_values'
  }

  getComponent() {
    return GenerateAIValuesContextItem
  }
}
