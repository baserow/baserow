import { Registerable } from '@baserow/modules/core/registry'

export class ServiceType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The integration type necessary to access this service.
   */
  get integrationType() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The form component to edit this service.
   */
  get formComponent() {
    return null
  }

  /**
   * Whether the service is valid.
   * @param service - The service object.
   * @returns {boolean} - If the service is valid.
   */
  isInError({ service }) {
    return false
  }

  /**
   * Whether the service returns a collection of records.
   */
  get returnsList() {
    return false
  }

  /**
   * In a service which returns a list, this method is used to
   * return the name of the given record.
   */
  getRecordName(service, record) {
    throw new Error('Must be set on the type.')
  }

  /**
   * In a service which returns a list, this method is used to
   * return the id of the given record.
   */
  getIdProperty(service, record) {
    throw new Error('Must be set on the type.')
  }

  /**
   * The maximum number of records that can be returned by this service
   */
  get maxResultLimit() {
    return 1
  }

  /**
   * This method can be used to process service data
   * in the frontend when displaying raw data
   * is not enough.
   */
  getResult(service, data) {
    return null
  }

  /**
   * Should return a JSON schema of the data returned by this service.
   */
  getDataSchema(applicationContext, service) {
    throw new Error('Must be set on the type.')
  }

  /**
   * A hook called prior to an update to modify the new values
   * before they get persisted in the API.
   */
  beforeUpdate(newValues, oldValues) {
    return newValues
  }

  /**
   * Returns a description of the given service
   */
  getDescription(service, application) {
    return this.name
  }

  getOrder() {
    return 0
  }
}
