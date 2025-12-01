import { Registerable } from '@baserow/modules/core/registry'

export class WorkflowActionType extends Registerable {
  get form() {
    return null
  }

  get label() {
    return null
  }

  get icon() {
    return null
  }

  /**
   * This function executes the action. This can happen in the frontend but also in the
   * backend, depending on what your action does.
   *
   * @param context {object} - Any additional information the action needs to execute
   * @returns {Promise<any> | void}
   */
  async execute(context) {
    return await Promise.resolve()
  }

  /**
   * Should return a JSON schema of the data returned by this workflow action.
   */
  getDataSchema(applicationContext, workflowAction) {
    throw new Error('Must be set on the type.')
  }

  /**
   * Allow to customize way data are accessed from workflow action
   */
  prepareValuePath(workflowAction, path) {
    return path
  }

  /**
   * Returns a message if the workflow action configuration is invalid.
   * @param {object} workflowAction - The workflow action to validate.
   * @param {object} params An object containing application context data.
   * @returns The error message or null if everything is good
   */
  getErrorMessage(workflowAction, applicationContext) {
    return null
  }

  /**
   * Returns whether the workflow action configuration is valid or not.
   * @param {object} workflowAction - The workflow action to validate.
   * @param {object} param An object containing application context data.
   * @returns true if the workflow action is in error
   */
  isInError(workflowAction, applicationContext) {
    return Boolean(this.getErrorMessage(workflowAction, applicationContext))
  }
}
