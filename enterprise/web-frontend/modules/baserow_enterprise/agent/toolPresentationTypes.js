import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import { DatabaseToolPresentationType } from '@baserow/modules/agent/toolPresentationTypes'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { RBACPaidFeature } from '@baserow_enterprise/paidFeatures'

/** Row comment tools, which require an Advanced workspace licence. */
class RowCommentToolPresentationType extends DatabaseToolPresentationType {
  get labelKey() {
    return `rowCommentTools.${this.constructor.definition.label}`
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': RBACPaidFeature.getType() },
    ]
  }
}

export class ListRowCommentsToolPresentationType extends RowCommentToolPresentationType {
  static definition = {
    type: 'list_row_comments',
    label: 'listRowComments',
    read: true,
    table: true,
    counted: STEP_STATUS.DONE,
  }
}

export class SearchRowCommentsToolPresentationType extends RowCommentToolPresentationType {
  static definition = {
    type: 'search_row_comments',
    label: 'searchRowComments',
    read: true,
    counted: STEP_STATUS.DONE,
  }
}

export class CreateRowCommentsToolPresentationType extends RowCommentToolPresentationType {
  static definition = {
    type: 'create_row_comments',
    label: 'createRowComments',
    counted: true,
    table: true,
  }
}
