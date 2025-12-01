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
import WorkspaceSettingsModal from '@baserow/modules/core/components/workspace/WorkspaceSettingsModal.vue'

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

  getDisabledClickModal(workspace) {
    return [WorkspaceSettingsModal, { workspace }]
  }

  getDisabledTooltip() {
    return 'Click to configure API key'
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

  getCompatibleFilterFieldType(field) {
    return this.getBaserowFieldType(field)
  }
}

export class PremiumFormulaFieldType extends FormulaFieldType {
  getAdditionalFormInputComponents() {
    return [FormulaFieldAI]
  }
}
