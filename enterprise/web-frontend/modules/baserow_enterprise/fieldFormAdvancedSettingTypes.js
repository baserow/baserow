import { FieldFormAdvancedSettingType } from '@baserow/modules/database/fieldFormAdvancedSettingTypes'
import SemanticSearchFieldSetting from '@baserow_enterprise/components/semanticSearch/SemanticSearchFieldSetting'

export class SemanticSearchFieldFormAdvancedSettingType extends FieldFormAdvancedSettingType {
  static getType() {
    return 'semantic_search'
  }

  get component() {
    return SemanticSearchFieldSetting
  }
}
