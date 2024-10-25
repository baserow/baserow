import { DataSyncType } from '@baserow/modules/database/dataSyncTypes'

import LocalBaserowTableDataSync from '@baserow_enterprise/components/dataSync/LocalBaserowTableDataSync'
import EnterpriseFeatures from '@baserow_enterprise/features'
import EnterpriseModal from '@baserow_enterprise/components/EnterpriseModal'
import JiraIssuesDataSyncForm from '@baserow_enterprise/components/dataSync/JiraIssuesDataSyncForm'
import GitHubIssuesDataSyncForm from '@baserow_enterprise/components/dataSync/GitHubIssuesDataSyncForm'

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
    return EnterpriseModal
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
    return EnterpriseModal
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
    return EnterpriseModal
  }
}
