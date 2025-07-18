import {
  DataSyncType,
  PostgreSQLDataSyncType as BasePostgreSQLDataSyncType,
} from '@baserow/modules/database/dataSyncTypes'

import LocalBaserowTableDataSync from '@baserow_enterprise/components/dataSync/LocalBaserowTableDataSync'
import EnterpriseFeatures from '@baserow_enterprise/features'
import JiraIssuesDataSyncForm from '@baserow_enterprise/components/dataSync/JiraIssuesDataSyncForm'
import GitHubIssuesDataSyncForm from '@baserow_enterprise/components/dataSync/GitHubIssuesDataSyncForm'
import GitLabIssuesDataSyncForm from '@baserow_enterprise/components/dataSync/GitLabIssuesDataSyncForm'
import HubspotContactsDataSyncForm from '@baserow_enterprise/components/dataSync/HubspotContactsDataSyncForm'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { DataSyncPaidFeature } from '@baserow_enterprise/paidFeatures'
import { RealtimePushTwoWaySyncStrategyType } from '@baserow_enterprise/twoWaySyncStrategyTypes'

export class LocalBaserowTableDataSyncType extends DataSyncType {
  static getType() {
    return 'local_baserow_table'
  }

  getIconClass() {
    return 'iconoir-menu'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('enterpriseDataSyncType.localBaserowTable')
  }

  getFormComponent() {
    return LocalBaserowTableDataSync
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.DATA_SYNC, workspaceId)
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': DataSyncPaidFeature.getType() },
    ]
  }
}

export class JiraIssuesDataSyncType extends DataSyncType {
  static getType() {
    return 'jira_issues'
  }

  getIconClass() {
    return 'baserow-icon-jira'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('enterpriseDataSyncType.jiraIssues')
  }

  getFormComponent() {
    return JiraIssuesDataSyncForm
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.DATA_SYNC, workspaceId)
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': DataSyncPaidFeature.getType() },
    ]
  }
}

export class GitHubIssuesDataSyncType extends DataSyncType {
  static getType() {
    return 'github_issues'
  }

  getIconClass() {
    return 'iconoir-github'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('enterpriseDataSyncType.githubIssues')
  }

  getFormComponent() {
    return GitHubIssuesDataSyncForm
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.DATA_SYNC, workspaceId)
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': DataSyncPaidFeature.getType() },
    ]
  }
}

export class GitLabIssuesDataSyncType extends DataSyncType {
  static getType() {
    return 'gitlab_issues'
  }

  getIconClass() {
    return 'baserow-icon-gitlab'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('enterpriseDataSyncType.gitlabIssues')
  }

  getFormComponent() {
    return GitLabIssuesDataSyncForm
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.DATA_SYNC, workspaceId)
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': DataSyncPaidFeature.getType() },
    ]
  }
}

export class HubspotContactsDataSyncType extends DataSyncType {
  static getType() {
    return 'hubspot_contacts'
  }

  getIconClass() {
    return 'baserow-icon-hubspot'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('enterpriseDataSyncType.hubspotContacts')
  }

  getFormComponent() {
    return HubspotContactsDataSyncForm
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.DATA_SYNC, workspaceId)
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': DataSyncPaidFeature.getType() },
    ]
  }
}

export class PostgreSQLDataSyncType extends BasePostgreSQLDataSyncType {
  getTwoWayDataSyncStrategy() {
    return RealtimePushTwoWaySyncStrategyType.getType()
  }
}
