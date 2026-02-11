import { Registerable } from '@baserow/modules/core/registry'
import AirtableImportForm from '@baserow/modules/database/components/airtable/AirtableImportForm'
import TemplateImportForm from '@baserow/modules/database/components/onboarding/TemplateImportForm'
import DatabaseTemplatePreview from '@baserow/modules/database/components/onboarding/DatabaseTemplatePreview'
import { DatabaseOnboardingType } from '@baserow/modules/database/onboardingTypes'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import AirtableService from '@baserow/modules/database/services/airtable'
import TemplateService from '@baserow/modules/core/services/template'

/**
 * Base class for database onboarding step types. Each type represents a different
 * way to initialize a database (scratch, import, airtable, template, AI, etc.).
 * These types control the UI segment selection and form rendering in DatabaseStep.vue.
 */
export class DatabaseOnboardingStepType extends Registerable {
  /**
   * The sort order for this step type. Lower values appear first.
   */
  getOrder() {
    throw new Error('getOrder must be implemented')
  }

  /**
   * The label displayed in the SegmentControl for this step type. Should return a
   * translated string.
   */
  getLabel() {
    throw new Error('getLabel must be implemented')
  }

  /**
   * The Vue component to render for this step type's form, or null if using the
   * default name input. Components like AirtableImportForm or TemplateImportForm
   * should be returned here.
   */
  getComponent() {
    return null
  }

  /**
   * Whether this step type should display the default name input field. Types like
   * 'scratch' and 'import' return true, while 'airtable' and 'template' return
   * false as they have their own components.
   */
  hasNameInput() {
    return false
  }

  /**
   * Determine whether this step type should be visible in the UI.
   * Can be used for conditional visibility based on feature flags, configuration, etc.
   */
  isVisible() {
    return true
  }

  /**
   * Validate the form data for this step type.
   * @param data - The current form data object
   * @param vuelidate - The vuelidate instance (v$) from the parent component
   * @param refs - The $refs object from the parent component for accessing child
   *  components
   * @returns {boolean} - True if the form is valid
   */
  isValid(data, vuelidate, refs) {
    throw new Error('isValid must be implemented')
  }

  /**
   * Get the preview component for this step type.
   * @param data - The data object containing all onboarding data
   * @returns {Component|null} - Vue component to show in preview, or null for default
   */
  getPreviewComponent(data) {
    return null
  }

  /**
   * Complete the onboarding for this step type after workspace creation.
   * This is called by DatabaseOnboardingType.complete() to handle type-specific logic.
   * @param workspace - The created workspace
   * @param stepData - The step data for this type
   * @param callback - Can be used to change the message on component while the
   *  onboarding is being processed.
   * @returns {Promise<object>} - Object to merge into returnValue (e.g., { job })
   */
  async completeAfterWorkspace(workspace, stepData, callback) {
    return {}
  }

  /**
   * Get the job for polling after completion.
   * @param data - The data object containing all onboarding form data
   * @param responses - The responses object from all completed steps
   * @returns {object|null} - Job object if async, null otherwise
   */
  getJobForPolling(data, responses) {
    return null
  }

  /**
   * Get the route to navigate to after completion.
   * @param data - The data object containing all onboarding form data
   * @param responses - The responses object from all completed steps (completed
   * job overwrites initial response)
   * @returns {object|null} - Route object or null
   */
  getCompletedRoute(data, responses) {
    return null
  }
}

export class ScratchDatabaseOnboardingStepType extends DatabaseOnboardingStepType {
  static getType() {
    return 'scratch'
  }

  getOrder() {
    return 100
  }

  getLabel() {
    return this.app.$i18n.t('databaseStep.scratch')
  }

  hasNameInput() {
    return true
  }

  isValid(data, vuelidate, refs) {
    return !vuelidate.$invalid && vuelidate.$dirty
  }
}

export class ImportDatabaseOnboardingStepType extends DatabaseOnboardingStepType {
  static getType() {
    return 'import'
  }

  getOrder() {
    return 200
  }

  getLabel() {
    return this.app.$i18n.t('databaseStep.import')
  }

  hasNameInput() {
    return true
  }

  isValid(data, vuelidate, refs) {
    return !vuelidate.$invalid && vuelidate.$dirty
  }
}

export class AirtableDatabaseOnboardingStepType extends DatabaseOnboardingStepType {
  static getType() {
    return 'airtable'
  }

  getOrder() {
    return 300
  }

  getLabel() {
    return this.app.$i18n.t('databaseStep.airtable')
  }

  getComponent() {
    return AirtableImportForm
  }

  hasNameInput() {
    return false
  }

  isValid(data, vuelidate, refs) {
    const component = refs.stepComponent
    return (
      !!component &&
      !!component.v$ &&
      !component.v$.$invalid &&
      component.v$.$dirty
    )
  }

  async completeAfterWorkspace(workspace, stepData) {
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

    return { job }
  }

  getJobForPolling(data, responses) {
    return responses[DatabaseOnboardingType.getType()]?.job
  }

  getCompletedRoute(data, responses) {
    // After job completion, the response IS the completed job (it overwrites the
    // original response)
    const completedJob = responses[DatabaseOnboardingType.getType()]
    const database = completedJob?.database
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
    return null
  }
}

export class TemplateDatabaseOnboardingStepType extends DatabaseOnboardingStepType {
  static getType() {
    return 'template'
  }

  getOrder() {
    return 400
  }

  getLabel() {
    return this.app.$i18n.t('databaseStep.template')
  }

  getComponent() {
    return TemplateImportForm
  }

  hasNameInput() {
    return false
  }

  isValid(data, vuelidate, refs) {
    const template = data[DatabaseOnboardingType.getType()].template
    return !!template
  }

  getPreviewComponent(data) {
    const template = data[DatabaseOnboardingType.getType()]?.template
    if (template) {
      return DatabaseTemplatePreview
    }
    return null
  }

  async completeAfterWorkspace(workspace, stepData) {
    const template = stepData.template
    const { data: job } = await TemplateService(this.app.$client).asyncInstall(
      workspace.id,
      template.id
    )
    return { job }
  }

  getJobForPolling(data, responses) {
    return responses[DatabaseOnboardingType.getType()]?.job
  }

  getCompletedRoute(data, responses) {
    // After job completion, the response is the completed job (it overwrites the
    // original response)
    const completedJob = responses[DatabaseOnboardingType.getType()]
    const database = completedJob?.installed_applications?.find(
      (application) => application.type === DatabaseApplicationType.getType()
    )

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
    return null
  }
}
