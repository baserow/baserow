import {
  OnboardingType,
  WorkspaceOnboardingType,
} from '@baserow/modules/core/onboardingTypes'

import DatabaseStep from '@baserow/modules/database/components/onboarding/DatabaseStep'
import DatabaseScratchTrackStep from '@baserow/modules/database/components/onboarding/DatabaseScratchTrackStep'
import DatabaseImportStep from '@baserow/modules/database/components/onboarding/DatabaseImportStep'
import DatabaseAppLayoutPreview from '@baserow/modules/database/components/onboarding/DatabaseAppLayoutPreview'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import ApplicationService from '@baserow/modules/core/services/application'
import TableService from '@baserow/modules/database/services/table'
import FieldService from '@baserow/modules/database/services/field'
import RowService from '@baserow/modules/database/services/row'
import AirtableService from '@baserow/modules/database/services/airtable'
import DatabaseScratchTrackFieldsStep from '@baserow/modules/database/components/onboarding/DatabaseScratchTrackFieldsStep.vue'
import DatabaseTemplatePreview from '@baserow/modules/database/components/onboarding/DatabaseTemplatePreview'
import TemplateService from '@baserow/modules/core/services/template'

const databaseTypeCondition = (data, type) => {
  const dependingType = DatabaseOnboardingType.getType()
  if (!Object.prototype.hasOwnProperty.call(data, dependingType)) {
    return true
  } else {
    return data[dependingType].type === type
  }
}

const createDatabase = async (data, responses, $client) => {
  const workspace = responses[WorkspaceOnboardingType.getType()]
  const databaseName = data[DatabaseOnboardingType.getType()].name

  const { data: database } = await ApplicationService($client).create(
    workspace.id,
    {
      type: DatabaseApplicationType.getType(),
      name: databaseName,
    }
  )

  return database
}

export class DatabaseOnboardingType extends OnboardingType {
  static getType() {
    return 'database'
  }

  getOrder() {
    return 2000
  }

  getFormComponent() {
    return DatabaseStep
  }

  getPreviewComponent(data) {
    const type = data[this.getType()]?.type
    const template = data[this.getType()]?.template
    if (type === 'template' && template) {
      return DatabaseTemplatePreview
    } else {
      return DatabaseAppLayoutPreview
    }
  }

  getAdditionalPreviewProps() {
    return { highlightDataName: 'applications' }
  }

  async complete(data, responses) {
    const workspace = responses[WorkspaceOnboardingType.getType()]
    const stepData = data[this.getType()]
    const fromType = stepData.type
    if (fromType === 'airtable') {
      const airtableUrl = stepData.airtableUrl
      const skipFiles = stepData.skipFiles
      const useSession = stepData.useSession
      const session = stepData.session
      const sessionSignature = stepData.sessionSignature
      const { data: job } = await AirtableService(this.app.$client).create(
        workspace.id,
        airtableUrl,
        skipFiles,
        useSession ? session : null,
        useSession ? sessionSignature : null
      )

      // Responds with the newly created job, so that the `getJobForPolling` can use
      // the response to mark the onboarding as an async job.
      return job
    } else if (fromType === 'template') {
      const template = stepData.template
      const { data: job } = await TemplateService(
        this.app.$client
      ).asyncInstall(workspace.id, template.id)

      // Responds with the newly created job, so that the `getJobForPolling` can use
      // the response to mark the onboarding as an async job.
      return job
    }
  }

  getJobForPolling(data, responses) {
    const type = data[this.getType()].type
    if (type === 'airtable' || type === 'template') {
      return responses[this.getType()]
    }
  }

  getCompletedRoute(data, responses) {
    const type = data[this.getType()].type
    let database = null
    if (type === 'airtable') {
      database = responses[this.getType()].database
    } else if (type === 'template') {
      database = responses[this.getType()].installed_applications.find(
        (application) => application.type === DatabaseApplicationType.getType()
      )
    }

    // Deliberately open the database first because that's where the user must start
    // their journey. If no database exist, return nothing, so that the dashboard
    // is opened.
    if (database) {
      const firstTableId = database.tables[0]?.id || 0
      return {
        name: 'database-table',
        params: {
          databaseId: database.id,
          tableId: firstTableId,
        },
      }
    }
  }
}

export class DatabaseScratchTrackOnboardingType extends OnboardingType {
  static getType() {
    return 'database_scratch_track'
  }

  getOrder() {
    return 2100
  }

  getFormComponent() {
    return DatabaseScratchTrackStep
  }

  getPreviewComponent() {
    return DatabaseAppLayoutPreview
  }

  condition(data) {
    return databaseTypeCondition(data, 'scratch')
  }

  async complete(data, responses) {
    const database = await createDatabase(data, responses, this.app.$client)
    const tableName = data[this.getType()].tableName
    const rows = data[this.getType()].rows

    const initialData = [['Name'], ...rows.map((name) => [name])]
    const { data: table } = await TableService(this.app.$client).createSync(
      database.id,
      {
        name: tableName,
      },
      initialData,
      true
    )

    return table
  }

  getCompletedRoute(data, responses) {
    return {
      name: 'database-table',
      params: {
        databaseId: responses[this.getType()].database_id,
        tableId: responses[this.getType()].id,
      },
    }
  }
}

export class DatabaseScratchTrackFieldsOnboardingType extends OnboardingType {
  static getType() {
    return 'database_scratch_track_fields'
  }

  getOrder() {
    return 2200
  }

  getFormComponent() {
    return DatabaseScratchTrackFieldsStep
  }

  getPreviewComponent() {
    return DatabaseAppLayoutPreview
  }

  condition(data) {
    return databaseTypeCondition(data, 'scratch')
  }

  canSkip() {
    return true
  }

  async complete(data, responses) {
    const tableData = responses[DatabaseScratchTrackOnboardingType.getType()]
    let onboardingTrackFieldsType
    try {
      onboardingTrackFieldsType = this.app.$registry.get(
        'onboardingTrackFields',
        `${this.getType()}_${tableData.name.toLowerCase()}`
      )
    } catch {
      onboardingTrackFieldsType = this.app.$registry.get(
        'onboardingTrackFields',
        `${this.getType()}_custom`
      )
    }

    const fieldParams = Object.values(data[this.getType()]?.fields || {})
    const items = [{ id: 1 }, { id: 2 }, { id: 3 }]

    for (const field of fieldParams) {
      const response = await FieldService(this.app.$client).create(
        tableData.id,
        field.props
      )

      onboardingTrackFieldsType.afterFieldCreated(field, response)

      field.rows.forEach((row, index) => {
        items[index][`field_${response.data.id}`] = row
      })
    }

    if (fieldParams.length > 0) {
      await RowService(this.app.$client).batchUpdate(tableData.id, items)
    }

    return tableData
  }

  getCompletedRoute(data, responses) {
    return {
      name: 'database-table',
      params: {
        databaseId: responses[this.getType()].database_id,
        tableId: responses[this.getType()].id,
      },
    }
  }
}

export class DatabaseImportOnboardingType extends OnboardingType {
  static getType() {
    return 'database_scratch_import'
  }

  getOrder() {
    return 2200
  }

  getFormComponent() {
    return DatabaseImportStep
  }

  getPreviewComponent() {
    return DatabaseAppLayoutPreview
  }

  condition(data) {
    return databaseTypeCondition(data, 'import')
  }

  async complete(data, responses) {
    const database = await createDatabase(data, responses, this.app.$client)
    const tableName = data[this.getType()].tableName
    const getData = data[this.getType()].getData
    const header = data[this.getType()].header
    const tableData = [header, ...(await getData())]

    const { data: job } = await TableService(this.app.$client).create(
      database.id,
      {
        name: tableName,
      },
      tableData,
      true
    )

    // Responds with the newly created job, so that the `getJobForPolling` can use
    // the response to mark the onboarding as an async job.
    return job
  }

  getJobForPolling(data, responses) {
    return responses[this.getType()]
  }

  getCompletedRoute(data, responses) {
    return {
      name: 'database-table',
      params: {
        databaseId: responses[this.getType()].database_id,
        tableId: responses[this.getType()].table_id,
      },
    }
  }
}
