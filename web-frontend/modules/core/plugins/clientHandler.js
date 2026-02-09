import axios from 'axios'
import { showError, useRuntimeConfig } from '#imports'

import { upperCaseFirst } from '@baserow/modules/core/utils/string'
import { makeRefreshAuthInterceptor } from '@baserow/modules/core/plugins/clientAuthRefresh'

export class ResponseErrorMessage {
  constructor(title, message) {
    this.title = title
    this.message = message
  }
}

/**
 * This class holds all the default error messages and offers the ability to
 * register new ones. This is stored in a separate class because need to inject
 * this, so it can be used by other modules.
 */
export class ClientErrorMap {
  constructor(app) {
    const { $i18n } = app
    // Declare the default error messages.
    this.errorMap = {
      ERROR_USER_NOT_IN_GROUP: new ResponseErrorMessage(
        $i18n.t('clientHandler.userNotInWorkspaceTitle'),
        $i18n.t('clientHandler.userNotInWorkspaceDescription')
      ),
      ERROR_USER_INVALID_GROUP_PERMISSIONS: new ResponseErrorMessage(
        $i18n.t('clientHandler.invalidWorkspacePermissionsTitle'),
        $i18n.t('clientHandler.invalidWorkspacePermissionsDescription')
      ),
      // @TODO move these errors to the module.
      ERROR_TABLE_DOES_NOT_EXIST: new ResponseErrorMessage(
        $i18n.t('clientHandler.tableDoesNotExistTitle'),
        $i18n.t('clientHandler.tableDoesNotExistDescription')
      ),
      ERROR_ROW_DOES_NOT_EXIST: new ResponseErrorMessage(
        $i18n.t('clientHandler.rowDoesNotExistTitle'),
        $i18n.t('clientHandler.rowDoesNotExistDescription')
      ),
      ERROR_CANNOT_CREATE_FIELD_TYPE: new ResponseErrorMessage(
        $i18n.t('clientHandler.cannotCreateFieldTypeTitle'),
        $i18n.t('clientHandler.cannotCreateFieldTypeDescription')
      ),
      ERROR_NOTIFICATION_DOES_NOT_EXIST: new ResponseErrorMessage(
        $i18n.t('clientHandler.notificationDoesNotExistTitle'),
        $i18n.t('clientHandler.notificationDoesNotExistDescription')
      ),
      ERROR_FILE_SIZE_TOO_LARGE: new ResponseErrorMessage(
        $i18n.t('clientHandler.fileSizeTooLargeTitle'),
        $i18n.t('clientHandler.fileSizeTooLargeDescription')
      ),
      ERROR_INVALID_FILE: new ResponseErrorMessage(
        $i18n.t('clientHandler.invalidFileTitle'),
        $i18n.t('clientHandler.invalidFileDescription')
      ),
      ERROR_FILE_URL_COULD_NOT_BE_REACHED: new ResponseErrorMessage(
        $i18n.t('clientHandler.fileUrlCouldNotBeReachedTitle'),
        $i18n.t('clientHandler.fileUrlCouldNotBeReachedDescription')
      ),
      ERROR_INVALID_FILE_URL: new ResponseErrorMessage(
        $i18n.t('clientHandler.invalidFileUrlTitle'),
        $i18n.t('clientHandler.invalidFileUrlDescription')
      ),
      USER_ADMIN_CANNOT_DEACTIVATE_SELF: new ResponseErrorMessage(
        $i18n.t('clientHandler.adminCannotDeactivateSelfTitle'),
        $i18n.t('clientHandler.adminCannotDeactivateSelfDescription')
      ),
      USER_ADMIN_CANNOT_DELETE_SELF: new ResponseErrorMessage(
        $i18n.t('clientHandler.adminCannotDeleteSelfTitle'),
        $i18n.t('clientHandler.adminCannotDeleteSelfDescription')
      ),
      USER_ADMIN_ALREADY_EXISTS: new ResponseErrorMessage(
        $i18n.t('clientHandler.adminAlreadyExistsTitle'),
        $i18n.t('clientHandler.adminAlreadyExistsDescription')
      ),
      ERROR_MAX_FIELD_COUNT_EXCEEDED: new ResponseErrorMessage(
        $i18n.t('clientHandler.maxFieldCountExceededTitle'),
        $i18n.t('clientHandler.maxFieldCountExceededDescription')
      ),
      ERROR_CANNOT_RESTORE_PARENT_BEFORE_CHILD: new ResponseErrorMessage(
        $i18n.t('clientHandler.cannotRestoreParentBeforeChildTitle'),
        $i18n.t('clientHandler.cannotRestoreParentBeforeChildDescription')
      ),
      ERROR_CANT_RESTORE_AS_RELATED_TABLE_TRASHED: new ResponseErrorMessage(
        $i18n.t('clientHandler.cannotRestoreAsRelatedTableTrashedTitle'),
        $i18n.t('clientHandler.cannotRestoreAsRelatedTableTrashedDescription')
      ),
      ERROR_GROUP_USER_IS_LAST_ADMIN: new ResponseErrorMessage(
        $i18n.t('clientHandler.workspaceUserIsLastAdminTitle'),
        $i18n.t('clientHandler.workspaceUserIsLastAdminDescription')
      ),
      ERROR_MAX_JOB_COUNT_EXCEEDED: new ResponseErrorMessage(
        $i18n.t('clientHandler.errorMaxJobCountExceededTitle'),
        $i18n.t('clientHandler.errorMaxJobCountExceededDescription')
      ),
      ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT: new ResponseErrorMessage(
        $i18n.t('clientHandler.failedToLockFieldDueToConflictTitle'),
        $i18n.t('clientHandler.failedToLockFieldDueToConflictDescription')
      ),
      ERROR_FAILED_TO_LOCK_TABLE_DUE_TO_CONFLICT: new ResponseErrorMessage(
        $i18n.t('clientHandler.failedToLockTableDueToConflictTitle'),
        $i18n.t('clientHandler.failedToLockTableDueToConflictDescription')
      ),
      ERROR_UNDO_REDO_LOCK_CONFLICT: new ResponseErrorMessage(
        $i18n.t('clientHandler.failedToUndoRedoDueToConflictTitle'),
        $i18n.t('clientHandler.failedToUndoRedoDueToConflictDescription')
      ),
      ERROR_MAXIMUM_SNAPSHOTS_REACHED: new ResponseErrorMessage(
        $i18n.t('clientHandler.maximumSnapshotsReachedTitle'),
        $i18n.t('clientHandler.maximumSnapshotsReachedDescription')
      ),
      ERROR_SNAPSHOT_IS_BEING_CREATED: new ResponseErrorMessage(
        $i18n.t('clientHandler.snapshotBeingCreatedTitle'),
        $i18n.t('clientHandler.snapshotBeingCreatedDescription')
      ),
      ERROR_SNAPSHOT_IS_BEING_RESTORED: new ResponseErrorMessage(
        $i18n.t('clientHandler.snapshotBeingRestoredTitle'),
        $i18n.t('clientHandler.snapshotBeingRestoredDescription')
      ),
      ERROR_SNAPSHOT_IS_BEING_DELETED: new ResponseErrorMessage(
        $i18n.t('clientHandler.snapshotBeingDeletedTitle'),
        $i18n.t('clientHandler.snapshotBeingDeletedDescription')
      ),
      ERROR_SNAPSHOT_NAME_NOT_UNIQUE: new ResponseErrorMessage(
        $i18n.t('clientHandler.snapshotNameNotUniqueTitle'),
        $i18n.t('clientHandler.snapshotNameNotUniqueDescription')
      ),
      ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED: new ResponseErrorMessage(
        $i18n.t('clientHandler.snapshotOperationLimitExceededTitle'),
        $i18n.t('clientHandler.snapshotOperationLimitExceededDescription')
      ),
      ERROR_AUTH_PROVIDER_DISABLED: new ResponseErrorMessage(
        $i18n.t('clientHandler.disabledPasswordProviderTitle'),
        $i18n.t('clientHandler.disabledPasswordProviderMessage')
      ),
      ERROR_OUTPUT_PARSER: new ResponseErrorMessage(
        $i18n.t('clientHandler.outputParserTitle'),
        $i18n.t('clientHandler.outputParserDescription')
      ),
      ERROR_GENERATIVE_AI_PROMPT: new ResponseErrorMessage(
        $i18n.t('clientHandler.generateAIPromptTitle'),
        $i18n.t('clientHandler.generateAIPromptDescription')
      ),
      // TODO: Move to enterprise module if possible
      ERROR_CANNOT_DISABLE_ALL_AUTH_PROVIDERS: new ResponseErrorMessage(
        $i18n.t('clientHandler.cannotDisableAllAuthProvidersTitle'),
        $i18n.t('clientHandler.cannotDisableAllAuthProvidersDescription')
      ),
      ERROR_MAX_LOCKS_PER_TRANSACTION_EXCEEDED: new ResponseErrorMessage(
        $i18n.t('clientHandler.maxLocksPerTransactionExceededTitle'),
        $i18n.t('clientHandler.maxLocksPerTransactionExceededDescription')
      ),
      ERROR_LAST_ADMIN_OF_GROUP: new ResponseErrorMessage(
        $i18n.t('clientHandler.lastAdminTitle'),
        $i18n.t('clientHandler.lastAdminMessage')
      ),
      ERROR_GENERATIVE_AI_DOES_NOT_EXIST: new ResponseErrorMessage(
        $i18n.t('clientHandler.generativeAIDoesNotExistTitle'),
        $i18n.t('clientHandler.generativeAIDoesNotExistDescription')
      ),
      ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE: new ResponseErrorMessage(
        $i18n.t('clientHandler.modelDoesNotBelongToTypeTitle'),
        $i18n.t('clientHandler.modelDoesNotBelongToTypeDescription')
      ),
      ERROR_MAX_NUMBER_OF_PENDING_WORKSPACE_INVITES_REACHED:
        new ResponseErrorMessage(
          $i18n.t(
            'clientHandler.maxNumberOfPendingWorkspaceInvitesReachedTitle'
          ),
          $i18n.t(
            'clientHandler.maxNumberOfPendingWorkspaceInvitesReachedDescription'
          )
        ),
      ERROR_FIELD_IS_ALREADY_PRIMARY: new ResponseErrorMessage(
        $i18n.t('clientHandler.fieldIsAlreadyPrimaryTitle'),
        $i18n.t('clientHandler.fieldIsAlreadyPrimaryDescription')
      ),
      ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE: new ResponseErrorMessage(
        $i18n.t('clientHandler.incompatiblePrimaryFieldTypeTitle'),
        $i18n.t('clientHandler.incompatiblePrimaryFieldTypeDescription')
      ),
      ERROR_CANNOT_CREATE_ROWS_IN_TABLE: new ResponseErrorMessage(
        $i18n.t('clientHandler.cannotCreateRowsInTableTitle'),
        $i18n.t('clientHandler.cannotCreateRowsInTableDescription')
      ),
      ERROR_DATABASE_DEADLOCK: new ResponseErrorMessage(
        $i18n.t('clientHandler.databaseDeadlockTitle'),
        $i18n.t('clientHandler.databaseDeadlockDescription')
      ),
      ERROR_UNIQUE_PRIMARY_PROPERTY_NOT_FOUND: new ResponseErrorMessage(
        $i18n.t('clientHandler.databaseUniquePrimaryPropertyNotFoundTitle'),
        $i18n.t(
          'clientHandler.databaseUniquePrimaryPropertyNotFoundDescription'
        )
      ),
      ERROR_FIELD_DATA_CONSTRAINT: new ResponseErrorMessage(
        $i18n.t('clientHandler.fieldDataConstraintTitle'),
        $i18n.t('clientHandler.fieldDataConstraintDescription')
      ),
      ERROR_FIELD_CONSTRAINT: new ResponseErrorMessage(
        $i18n.t('clientHandler.fieldConstraintTitle'),
        $i18n.t('clientHandler.fieldConstraintDescription')
      ),
    }
  }

  setError(code, title, description) {
    this.errorMap[code] = new ResponseErrorMessage(title, description)
  }
}

export class ErrorHandler {
  constructor(
    store,
    app,
    clientErrorMap,
    response,
    code = null,
    detail = null
  ) {
    this.isHandled = false
    this.store = store
    this.app = app
    this.response = response
    this.setError(code, detail)
    this.errorMap = clientErrorMap.errorMap

    // A temporary notFoundMap containing the error messages for when the
    // response contains a 404 error based on the provided context name. Note
    // that an entry is not found a default message will be generated.
    this.notFoundMap = {}
  }

  /**
   * Changes the error code and details.
   */
  setError(code, detail) {
    this.code = code
    this.detail = detail
  }

  hasBaserowAPIError() {
    return this.response !== undefined && this.code != null
  }

  hasRequestBodyValidationError() {
    return (
      this.response !== undefined &&
      this.response?.data?.error === 'ERROR_REQUEST_BODY_VALIDATION'
    )
  }

  /**
   * Returns true is the response status code is equal to not found (404).
   * @return {boolean}
   */
  isNotFound() {
    return this.response !== undefined && this.response.status === 404
  }

  /**
   * Returns true if the response status code is equal to not found (429) which
   * means that the user is sending too much requests to the server.
   * @return {boolean}
   */
  isTooManyRequests() {
    return this.response !== undefined && this.response.status === 429
  }

  /**
   * Return true if there is a network error.
   * @return {boolean}
   */
  hasNetworkError() {
    return this.response === undefined
  }

  /**
   * Finds a message in the global errors or in the provided specific error map.
   */
  getErrorMessage(specificErrorMap = null) {
    if (
      specificErrorMap !== null &&
      Object.prototype.hasOwnProperty.call(specificErrorMap, this.code)
    ) {
      return specificErrorMap[this.code]
    }

    if (Object.prototype.hasOwnProperty.call(this.errorMap, this.code)) {
      return this.errorMap[this.code]
    }

    return this.genericDefaultError()
  }

  searchForMatchingFieldException(
    listOfDetailErrors,
    mapOfDetailCodeToResponseError
  ) {
    for (const detailError of listOfDetailErrors) {
      if (
        detailError &&
        typeof detailError === 'object' &&
        typeof detailError.code === 'string'
      ) {
        const handledError = mapOfDetailCodeToResponseError[detailError.code]
        if (handledError) {
          return handledError
        }
      }
    }
    return null
  }

  /**
   * Given a "ERROR_REQUEST_BODY_VALIDATION" error has occurred this function matches
   * a provided error map against the machine readable error codes in the "detail"
   * key in the response.
   *
   * For example if the response contains an error looking like:
   *
   * {
   *   "error": "ERROR_REQUEST_BODY_VALIDATION",
   *   "detail": {
   *     "url": [
   *       {
   *         "error": "Enter a valid URL.",
   *         "code": "invalid"
   *       }
   *     ]
   *   }
   * }
   *
   * Then you would call this function like so to match the above error and get your
   * ResponseErrorMessage returned:
   *
   * getRequestBodyErrorMessage({"url":{"invalid": new ResponseErrorMessage('a','b')}})
   *
   * @param requestBodyErrorMap An object where it's keys are the names of the
   * request body attribute that can fail with a value being another sub object. This
   * sub object should be keyed by the "code" returned in the error detail with the
   * value being a ResponseErrorMessage that should be returned if the API returned an
   * error for that attribute and code.
   * @return Any The first ResponseErrorMessage which is found in the error map that
   * matches an error in the response body, or null if no match is found.
   */
  getRequestBodyErrorMessage(requestBodyErrorMap) {
    const detail = this.response?.data?.detail

    if (requestBodyErrorMap && detail && typeof detail === 'object') {
      for (const fieldName of Object.keys(detail)) {
        const errorsForField = detail[fieldName]
        const supportedExceptionsForField = requestBodyErrorMap[fieldName]

        if (
          errorsForField != null &&
          Array.isArray(errorsForField) &&
          supportedExceptionsForField
        ) {
          const matchingException = this.searchForMatchingFieldException(
            errorsForField,
            supportedExceptionsForField
          )
          if (matchingException) {
            return matchingException
          }
        }
      }
    }

    return null
  }

  /**
   * Finds a not found message for a given context.
   */
  getNotFoundMessage(name) {
    if (!Object.prototype.hasOwnProperty.call(this.notFoundMap, name)) {
      return new ResponseErrorMessage(
        this.app.$i18n.t('clientHandler.notFoundTitle', {
          name: upperCaseFirst(name),
        }),
        this.app.$i18n.t('clientHandler.notFoundDescription', {
          name: name.toLowerCase(),
        })
      )
    }
    return this.notFoundMap[name]
  }

  /**
   * Returns a standard network error message. For example if the API server
   * could not be reached.
   */
  getNetworkErrorMessage() {
    return new ResponseErrorMessage(
      this.app.$i18n.t('clientHandler.networkErrorTitle'),
      this.app.$i18n.t('clientHandler.networkErrorDescription')
    )
  }

  /**
   * Returns a standard network error message. For example if the API server
   * could not be reached.
   */
  getTooManyRequestsError() {
    return new ResponseErrorMessage(
      this.app.$i18n.t('clientHandler.tooManyRequestsTitle'),
      this.app.$i18n.t('clientHandler.tooManyRequestsDescription')
    )
  }

  /**
   * If there is an error or the requested detail is not found an error
   * message related to the problem is returned.
   */
  getMessage(name = null, specificErrorMap = null, requestBodyErrorMap = null) {
    if (this.isTooManyRequests()) {
      return this.getTooManyRequestsError()
    }
    if (this.hasNetworkError()) {
      return this.getNetworkErrorMessage()
    }
    if (this.hasBaserowAPIError()) {
      if (this.hasRequestBodyValidationError()) {
        const matchingRequestBodyError =
          this.getRequestBodyErrorMessage(requestBodyErrorMap)
        if (matchingRequestBodyError) {
          return matchingRequestBodyError
        }
      }
      return this.getErrorMessage(specificErrorMap)
    }
    if (this.isNotFound()) {
      return this.getNotFoundMessage(name)
    }
    return this.genericDefaultError()
  }

  genericDefaultError() {
    return new ResponseErrorMessage(
      this.app.$i18n.t('clientHandler.notCompletedTitle'),
      this.app.$i18n.t('clientHandler.notCompletedDescription')
    )
  }

  /**
   * If there is an error or the requested detail is not found we will try to
   * get find an existing message of one is not provided and notify the user
   * about what went wrong. After that the error is marked as handled.
   */
  notifyIf(name = null, message = null) {
    if (
      !(
        this.hasBaserowAPIError() ||
        this.hasNetworkError() ||
        this.isNotFound()
      ) ||
      this.isHandled
    ) {
      return
    }

    if (message === null) {
      message = this.getMessage(name)
    }

    this.store.dispatch(
      'toast/error',
      {
        title: message.title,
        message: message.message,
      },
      { root: true }
    )

    this.handled()
  }

  /**
   * Will mark the error as handled so that the same error message isn't shown
   * twice.
   */
  handled() {
    this.isHandled = true
  }
}

export function makeErrorResponseInterceptor(
  store,
  app,
  clientErrorMap,
  nuxtErrorHandler
) {
  return (error) => {
    const rspData = error.response?.data

    // user session expired. Redirect to login page to start a new session.
    if (rspData?.error === 'ERROR_INVALID_REFRESH_TOKEN') {
      nuxtErrorHandler({ statusCode: 401, message: 'User session expired' })
      return Promise.reject(error)
    }

    error.handler = new ErrorHandler(store, app, clientErrorMap, error.response)
    if (
      typeof rspData === 'object' &&
      'error' in rspData &&
      'detail' in rspData
    ) {
      error.handler.setError(rspData.error, rspData.detail)
    } else if (typeof rspData !== 'object') {
      error.handler.setError(500, null)
    }

    return Promise.reject(error)
  }
}

/**
 * Add the user related headers according to the current authentication status.
 */
const prepareRequestHeaders = (store) => (config) => {
  const application = store.getters['userSourceUser/getCurrentApplication']
  if (store.getters['auth/isAuthenticated']) {
    const token = store.getters['auth/token']
    config.headers.Authorization = `JWT ${token}`
    config.headers.ClientSessionId =
      store.getters['auth/getUntrustedClientSessionId']
    // If we are logged with Baserow user and with a user source user
    // so we also want to send this user token
    // to the backend through the custom `UserSourceAuthorization` header.
    // This enables the "double" authentication.
    // We access the data with the permission of the currently logged Baserow user
    // but we can see the data of the user source user.
    if (store.getters['userSourceUser/isAuthenticated'](application)) {
      const userSourceToken =
        store.getters['userSourceUser/accessToken'](application)
      config.headers.UserSourceAuthorization = `JWT ${userSourceToken}`
    }
  } else if (store.getters['userSourceUser/isAuthenticated'](application)) {
    // Here we are logged as a user source user
    const userSourceToken =
      store.getters['userSourceUser/accessToken'](application)
    // We don't want to add the user source token if we are refreshing as the token
    // won't be accepted.
    if (!store.getters['userSourceUser/isRefreshing'](application)) {
      config.headers.Authorization = `JWT ${userSourceToken}`
    }
  }
  if (store.getters['auth/webSocketId'] !== null) {
    const webSocketId = store.getters['auth/webSocketId']
    config.headers.WebSocketId = webSocketId
  }

  return config
}

const createAxiosInstance = (runtimeConfig) => {
  const publicBackendUrl = runtimeConfig.public.publicBackendUrl

  const baseBackendUrl = import.meta.client
    ? publicBackendUrl
    : runtimeConfig.privateBackendUrl || publicBackendUrl
  const url = `${baseBackendUrl || ''}/api`

  return axios.create({
    baseURL: url,
    withCredentials: false,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
  })
}

export default defineNuxtPlugin({
  name: 'client-handler',
  dependsOn: ['i18n', 'create-store'],
  async setup(nuxtApp) {
    const runtimeConfig = useRuntimeConfig()
    const store = nuxtApp.$store

    const client = createAxiosInstance(runtimeConfig)

    const clientErrorMap = new ClientErrorMap(nuxtApp)

    client.interceptors.request.use(prepareRequestHeaders(store))

    client.interceptors.response.use(
      null,
      makeErrorResponseInterceptor(store, nuxtApp, clientErrorMap, showError)
    )

    const shouldInterceptRequest = () =>
      store.getters['auth/shouldRefreshToken']()

    const shouldInterceptResponse = (error) =>
      store.getters['auth/isAuthenticated'] &&
      error.response?.data?.error === 'ERROR_INVALID_ACCESS_TOKEN'

    const refreshToken = async () => await store.dispatch('auth/refresh')

    const refreshAuthInterceptor = makeRefreshAuthInterceptor(
      client,
      refreshToken,
      shouldInterceptRequest,
      shouldInterceptResponse
    )
    client.interceptors.response.use(null, refreshAuthInterceptor)

    const shouldInterceptUserSourceRequest = (req) => {
      const application = store.getters['userSourceUser/getCurrentApplication']
      return (
        !store.getters['auth/isAuthenticated'] &&
        store.getters['userSourceUser/shouldRefreshToken'](application)
      )
    }

    const shouldInterceptUserSourceResponse = (error) => {
      const application = store.getters['userSourceUser/getCurrentApplication']
      return (
        !store.getters['auth/isAuthenticated'] &&
        store.getters['userSourceUser/isAuthenticated'](application) &&
        error.response?.data?.error === 'ERROR_INVALID_ACCESS_TOKEN'
      )
    }
    const refreshUserSourceToken = async () =>
      await store.dispatch('userSourceUser/refreshAuth', {
        application: store.getters['userSourceUser/getCurrentApplication'],
      })

    const refreshUserSourceUserInterceptor = makeRefreshAuthInterceptor(
      client,
      refreshUserSourceToken,
      shouldInterceptUserSourceRequest,
      shouldInterceptUserSourceResponse
    )
    client.interceptors.response.use(null, refreshUserSourceUserInterceptor)

    return {
      provide: {
        client,
        clientErrorMap,
      },
    }
  },
})
