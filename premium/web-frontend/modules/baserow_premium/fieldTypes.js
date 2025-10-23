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
import PremiumFeatures from '@baserow_premium/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { AIPaidFeature } from '@baserow_premium/paidFeatures'
import _ from 'lodash'

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

  isReadOnlyField(field) {
    if (field && _.isBoolean(field.read_only)) {
      return field.read_only
    }
    return false
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

  getBaserowFieldType(field) {
    return this.app.$registry
      .get('aiFieldOutputType', field.ai_output_type)
      .getBaserowFieldType()
  }

  getCardComponent(field) {
    return this.getBaserowFieldType(field).getCardComponent(field)
  }

  getRowHistoryEntryComponent(field) {
    return null
  }

  getFormViewFieldComponents(field) {
    return {}
  }

  getDefaultValue(field) {
    return null
  }

  getCardValueHeight(field) {
    return this.getBaserowFieldType(field).getCardValueHeight(field)
  }

  getSort(name, order, field) {
    return this.getBaserowFieldType(field).getSort(name, order, field)
  }

  getCanSortInView(field) {
    return this.getBaserowFieldType(field).getCanSortInView(field)
  }

  getDocsDataType(field) {
    return this.getBaserowFieldType(field).getDocsDataType(field)
  }

  getDocsDescription(field) {
    const { i18n } = this.app
    return i18n.t('premiumFieldType.aiDescription')
  }

  getDocsRequestExample(field) {
    return 'read only'
  }

  getDocsResponseExample(field) {
    return this.getBaserowFieldType(field).getDocsResponseExample(field)
  }

  prepareValueForCopy(field, value) {
    return this.getBaserowFieldType(field).prepareValueForCopy(field, value)
  }

  getContainsFilterFunction(field) {
    return this.getBaserowFieldType(field).getContainsFilterFunction(field)
  }

  getContainsWordFilterFunction(field) {
    return this.getBaserowFieldType(field).getContainsWordFilterFunction(field)
  }

  toHumanReadableString(field, value) {
    return this.getBaserowFieldType(field).toHumanReadableString(field, value)
  }

  getSortIndicator(field) {
    return this.getBaserowFieldType(field).getSortIndicator(field)
  }

  canRepresentDate(field) {
    return this.getBaserowFieldType(field).canRepresentDate(field)
  }

  getCanGroupByInView(field) {
    return this.getBaserowFieldType(field).getCanGroupByInView(field)
  }

  parseInputValue(field, value) {
    return this.getBaserowFieldType(field).parseInputValue(field, value)
  }

  canRepresentFiles(field) {
    return this.getBaserowFieldType(field).canRepresentFiles(field)
  }

  getHasEmptyValueFilterFunction(field) {
    return this.getBaserowFieldType(field).getHasEmptyValueFilterFunction(field)
  }

  getHasValueContainsFilterFunction(field) {
    return this.getBaserowFieldType(field).getHasValueContainsFilterFunction(
      field
    )
  }

  getHasValueContainsWordFilterFunction(field) {
    return this.getBaserowFieldType(
      field
    ).getHasValueContainsWordFilterFunction(field)
  }

  getHasValueLengthIsLowerThanFilterFunction(field) {
    return this.getBaserowFieldType(
      field
    ).getHasValueLengthIsLowerThanFilterFunction(field)
  }

  getGroupByComponent(field) {
    return this.getBaserowFieldType(field).getGroupByComponent(field)
  }

  getRowValueFromGroupValue(field, value) {
    return this.getBaserowFieldType(field).getRowValueFromGroupValue(
      field,
      value
    )
  }

  getGroupValueFromRowValue(field, value) {
    return this.getBaserowFieldType(field).getGroupValueFromRowValue(
      field,
      value
    )
  }

  isEqual(field, value1, value2) {
    return this.getBaserowFieldType(field).isEqual(field, value1, value2)
  }

  parseFilterValue(field, filterValue) {
    return this.getBaserowFieldType(field).parseFilterValue(field, filterValue)
  }

  formatFilterValue(field, value) {
    return this.getBaserowFieldType(field).formatFilterValue(field, value)
  }

  canBeReferencedByFormulaField(field) {
    return this.getBaserowFieldType(field).canBeReferencedByFormulaField(field)
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
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': AIPaidFeature.getType() },
    ]
  }

  prepareValueForUpdate(field, value) {
    return this.getBaserowFieldType(field).prepareValueForUpdate(field, value)
  }

  prepareValueForPaste(field, value) {
    return this.getBaserowFieldType(field).prepareValueForPaste(field, value)
  }

  /**
   * Hook method called by ViewFilterType.fieldIsCompatible() to determine if this
   * field type supports a given filter.
   *
   * This implements the same pattern as the backend's is_compatible_with_filter_type
   * hook - allowing premium field types to declare filter compatibility without
   * core being aware of them.
   *
   * AI fields delegate to their underlying field type based on output type:
   * - text output → long_text field type
   * - choice output → single_select field type (not yet supported)
   *
   * We check if the filter's compatible field types include the underlying type.
   *
   * @param {Object} field - The field instance being checked
   * @param {ViewFilterType} filterType - The filter type being checked
   * @return {boolean} - True if this field is compatible with the filter
   */
  isCompatibleWithFilter(field, filterType) {
    // Only support text output type
    if (field.ai_output_type !== 'text') {
      return false
    }

    // Get the underlying field type that AI delegates to based on output type
    const baserowFieldType = this.getBaserowFieldType(field)
    const underlyingType = baserowFieldType.getType()

    // Check if the filter is compatible with the underlying field type
    return filterType.compatibleFieldTypes.includes(underlyingType)
  }
}

export class PremiumFormulaFieldType extends FormulaFieldType {
  getAdditionalFormInputComponents() {
    return [FormulaFieldAI]
  }
}
