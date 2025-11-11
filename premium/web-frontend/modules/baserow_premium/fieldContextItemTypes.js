import { Registerable } from '@baserow/modules/core/registry'
import RegenerateAIFieldContextItem from '@baserow_premium/components/field/RegenerateAIFieldContextItem'

export class RegenerateAIFieldContextItemType extends Registerable {
  static getType() {
    return 'regenerate_ai_field'
  }

  getComponent() {
    return RegenerateAIFieldContextItem
  }
}
