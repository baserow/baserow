import {
  FieldType,
  FormulaFieldType,
} from '@baserow/modules/database/fieldTypes'

import GridViewFieldAI from '@baserow_premium/components/views/grid/fields/GridViewFieldAI'
import FunctionalGridViewFieldAI from '@baserow_premium/components/views/grid/fields/FunctionalGridViewFieldAI'
import RowEditFieldAI from '@baserow_premium/components/row/RowEditFieldAI'
import FieldAISubForm from '@baserow_premium/components/field/FieldAISubForm'
import FormulaFieldAI from '@baserow_premium/components/field/FormulaFieldAI'
import GridViewFieldAIGenerateValuesContextItem from '@baserow_premium/components/views/grid/fields/GridViewFieldAIGenerateValuesContextItem'
import PremiumModal from '@baserow_premium/components/PremiumModal'
import PremiumFeatures from '@baserow_premium/features'

export class AIFieldType extends FieldType {
  static getType() {
    return 'ai'
  }

  getIconClass() {
    return 'iconoir-magic-wand'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('premiumFieldType.ai')
  }

  getIsReadOnly() {
    return true
  }

  getGridViewFieldComponent() {
    return GridViewFieldAI
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldAI
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldAI
  }

  getFormComponent() {
    return FieldAISubForm
  }

  getCardComponent(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getCardComponent(field)
  }

  getRowHistoryEntryComponent(field) {
    return null
  }

  getFormViewFieldComponents(field) {
    return {}
  }

  getEmptyValue(field) {
    return null
  }

  getCardValueHeight(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getCardValueHeight(field)
  }

  getSort(name, order, field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getSort(name, order, field)
  }

  getCanSortInView(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getCanSortInView(field)
  }

  getDocsDataType(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getDocsDataType(field)
  }

  getDocsDescription(field) {
    const { i18n } = this.app
    return i18n.t('premiumFieldType.aiDescription')
  }

  getDocsRequestExample(field) {
    return 'read only'
  }

  getDocsResponseExample(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getDocsResponseExample(field)
  }

  prepareValueForCopy(field, value) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .prepareValueForCopy(field, value)
  }

  getContainsFilterFunction(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getContainsFilterFunction(field)
  }

  getContainsWordFilterFunction(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getContainsWordFilterFunction(field)
  }

  toHumanReadableString(field, value) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .toHumanReadableString(field, value)
  }

  getSortIndicator(field, registry) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getSortIndicator(field, registry)
  }

  canRepresentDate(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .canRepresentDate(field)
  }

  getCanGroupByInView(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getCanGroupByInView(field)
  }

  parseInputValue(field, value) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .parseInputValue(field, value)
  }

  canRepresentFiles(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .canRepresentFiles(field)
  }

  getHasEmptyValueFilterFunction(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getHasEmptyValueFilterFunction(field)
  }

  getHasValueContainsFilterFunction(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getHasValueContainsFilterFunction(field)
  }

  getHasValueContainsWordFilterFunction(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getHasValueContainsWordFilterFunction(field)
  }

  getHasValueLengthIsLowerThanFilterFunction(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getHasValueLengthIsLowerThanFilterFunction(field)
  }

  getGroupByComponent(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getGroupByComponent(field)
  }

  getGroupByIndicator(field, registry) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getGroupByIndicator(field, registry)
  }

  getRowValueFromGroupValue(field, value) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getRowValueFromGroupValue(field, value)
  }

  getGroupValueFromRowValue(field, value) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .getGroupValueFromRowValue(field, value)
  }

  isEqual(field, value1, value2) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .isEqual(field, value1, value2)
  }

  canBeReferencedByFormulaField(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
      .canBeReferencedByFormulaField(field)
  }

  getGridViewContextItemsOnCellsSelection(field) {
    return [GridViewFieldAIGenerateValuesContextItem]
  }

  isEnabled(workspace) {
    return Object.values(workspace.generative_ai_models_enabled).some(
      (models) => models.length > 0
    )
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(PremiumFeatures.PREMIUM, workspaceId)
  }

  getDeactivatedClickModal(workspaceId) {
    return PremiumModal
  }
}

export class PremiumFormulaFieldType extends FormulaFieldType {
  getAdditionalFormInputComponents() {
    return [FormulaFieldAI]
  }
}
