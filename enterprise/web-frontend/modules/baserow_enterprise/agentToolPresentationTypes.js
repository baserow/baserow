import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import { ActionToolPresentationType } from '@baserow/modules/agent/toolPresentationTypes'
import LocalBaserowNodeServiceForm from '@baserow/modules/automation/components/workflow/LocalBaserowNodeServiceForm'

export class LocalBaserowSemanticSearchToolPresentationType extends ActionToolPresentationType {
  static getType() {
    return 'local_baserow_semantic_search'
  }

  get fieldLabels() {
    return {
      table: 'localBaserowTableSelector.tableFieldLabel',
      search_query: 'localBaserowSemanticSearchForm.searchQuery',
      max_results: 'localBaserowSemanticSearchForm.maxResults',
      integration_id: 'localBaserowServiceForm.integrationDropdownLabel',
      table_id: 'localBaserowTableSelector.tableFieldLabel',
      search_field_ids: 'localBaserowSemanticSearchForm.fields',
      filters: 'agentSemanticSearch.filters',
    }
  }

  getLabel(t) {
    return t('agentSemanticSearch.tool')
  }

  getActivity({ status }, t) {
    return t(
      status === STEP_STATUS.RUNNING
        ? 'agentSemanticSearch.toolRunning'
        : status === STEP_STATUS.DONE
          ? 'agentSemanticSearch.toolDone'
          : 'agentSemanticSearch.tool'
    )
  }

  /** The search form only picks a table, so the integration is picked first. */
  getFormComponent() {
    return LocalBaserowNodeServiceForm
  }
}
