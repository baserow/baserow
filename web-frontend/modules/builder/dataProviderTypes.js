import _ from 'lodash'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { getValueAtPath } from '@baserow/modules/core/utils/object'

import { defaultValueForParameterType } from '@baserow/modules/builder/utils/params'
import { DEFAULT_USER_ROLE_PREFIX } from '@baserow/modules/builder/constants'
import {
  PAGE_PARAM_TYPE_VALIDATION_FUNCTIONS,
  QUERY_PARAM_TYPE_HANDLER_FUNCTIONS,
} from '@baserow/modules/builder/enums'
import { extractSubSchema } from '@baserow/modules/core/utils/schema'
import { handleDispatchError } from '@baserow/modules/builder/utils/error'

export class DataSourceDataProviderType extends DataProviderType {
  constructor(...args) {
    super(...args)
    this.debouncedFetches = {}
  }

  static getType() {
    return 'data_source'
  }

  get needBackendContext() {
    return true
  }

  get name() {
    return this.app.i18n.t('dataProviderType.dataSource')
  }

  showDataSourceErrors(page, failedDataSources) {
    failedDataSources.forEach(({ id, error }) => {
      const fakeError = { response: { data: error } }
      const dataSource = this.app.store.getters[
        'dataSource/getPageDataSourceById'
      ](page, id)
      const dataSourceName = dataSource?.name || `Data Source ${id}`
      handleDispatchError(
        fakeError,
        this.app,
        this.app.i18n.t('builderToast.errorDataSourceDispatch', {
          name: dataSourceName,
        })
      )
    })
  }

  /**
   * Dispatch all the shared data sources.
   * @param {Object} applicationContext
   */
  async initOnce(applicationContext) {
    const page = this.app.store.getters['page/getSharedPage'](
      applicationContext.builder
    )

    const dataSources =
      this.app.store.getters['dataSource/getPageDataSources'](page)

    const failedDataSources = await this.app.store.dispatch(
      'dataSourceContent/fetchPageDataSourceContent',
      {
        page,
        data: DataProviderType.getAllDataSourceDispatchContext(
          this.app.$registry.getAll('builderDataProvider'),
          applicationContext
        ),
        dataSources,
        mode: applicationContext.mode,
      }
    )

    this.showDataSourceErrors(page, failedDataSources)
  }

  /**
   * Dispatch all the data source of the current page only (not the shared ones).
   * @param {Object} applicationContext
   */
  async init(applicationContext) {
    const dataSources = this.app.store.getters['dataSource/getPageDataSources'](
      applicationContext.page
    )

    // Dispatch the data sources
    const failedDataSources = await this.app.store.dispatch(
      'dataSourceContent/fetchPageDataSourceContent',
      {
        page: applicationContext.page,
        data: DataProviderType.getAllDataSourceDispatchContext(
          this.app.$registry.getAll('builderDataProvider'),
          applicationContext
        ),
        dataSources,
        mode: applicationContext.mode,
      }
    )

    this.showDataSourceErrors(applicationContext.page, failedDataSources)
  }

  getDataSourceDispatchContext(applicationContext) {
    const { element } = applicationContext
    // If the workflow action dispatch comes from a collection element, we
    // need to pass it to the backend for validating adhoc refinements.
    if (element) {
      return { element: element.id }
    }
    return null
  }

  getDataChunk(applicationContext, [dataSourceId, ...rest]) {
    const pages = [
      applicationContext.page,
      this.app.store.getters['page/getSharedPage'](applicationContext.builder),
    ]

    const dataSource = this.app.store.getters[
      'dataSource/getPagesDataSourceById'
    ](pages, parseInt(dataSourceId))

    const content = this.getDataSourceContent(applicationContext, dataSource)

    let preparedPath

    if (!content) {
      return null
    }

    const serviceType = this.app.$registry.get('service', dataSource.type)

    if (serviceType.returnsList) {
      // if it returns a list let's consume the next path token which is the row
      if (rest.length >= 2) {
        const [row, ...afterRow] = rest
        preparedPath = [
          row,
          ...serviceType.prepareValuePath(dataSource, afterRow),
        ]
      } else {
        preparedPath = rest
      }
    } else {
      preparedPath = serviceType.prepareValuePath(dataSource, rest)
    }

    return getValueAtPath(content, preparedPath)
  }

  getDataSourceContent(applicationContext, dataSource) {
    if (!dataSource?.type) {
      return null
    }

    const page = this.app.store.getters['page/getById'](
      applicationContext.builder,
      dataSource.page_id
    )

    const dataSourceContents =
      this.app.store.getters['dataSourceContent/getDataSourceContents'](page)

    const serviceType = this.app.$registry.get('service', dataSource.type)

    if (serviceType.returnsList) {
      return dataSourceContents[dataSource.id]?.results
    } else {
      return dataSourceContents[dataSource.id]
    }
  }

  getDataSourceSchema(dataSource) {
    if (dataSource?.type) {
      const serviceType = this.app.$registry.get('service', dataSource.type)
      return serviceType.getDataSchema(dataSource)
    }
    return null
  }

  getDataContent(applicationContext) {
    const pages = [
      applicationContext.page,
      this.app.store.getters['page/getSharedPage'](applicationContext.builder),
    ]

    const dataSources =
      this.app.store.getters['dataSource/getPagesDataSources'](pages)

    return Object.fromEntries(
      dataSources.map((dataSource) => {
        return [
          dataSource.id,
          this.getDataSourceContent(applicationContext, dataSource),
        ]
      })
    )
  }

  getDataSchema(applicationContext) {
    const pages = [
      this.app.store.getters['page/getSharedPage'](applicationContext.builder),
      applicationContext.page,
    ]

    const allDataSources =
      this.app.store.getters['dataSource/getPagesDataSources'](pages)

    // If we have a data source id in the application context we keep data sources
    // until this one because we can't use the ones after
    const dataSources = applicationContext.dataSource?.id
      ? _.takeWhile(
          allDataSources,
          ({ id }) => id !== applicationContext.dataSource.id
        )
      : allDataSources

    const result = Object.fromEntries(
      dataSources
        .map((dataSource, index) => {
          const dsSchema = this.getDataSourceSchema(dataSource)
          if (dsSchema) {
            // We don't use the schema directly as it comes from the store and can't
            // be mutated
            return [dataSource.id, { ...dsSchema, order: index }]
          }
          return [dataSource.id, null]
        })
        .filter(([, schema]) => schema)
    )

    return { type: 'object', properties: result }
  }

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 2) {
      const dataSourceId = parseInt(pathParts[1])
      const pages = [
        applicationContext.page,
        this.app.store.getters['page/getSharedPage'](
          applicationContext.builder
        ),
      ]
      const dataSource = this.app.store.getters[
        'dataSource/getPagesDataSourceById'
      ](pages, dataSourceId)

      if (dataSource) {
        return dataSource.name
      }

      return `data_source_${dataSourceId}`
    }
    return super.getPathTitle(applicationContext, pathParts)
  }
}

export class DataSourceContextDataProviderType extends DataProviderType {
  static getType() {
    return 'data_source_context'
  }

  get name() {
    return this.app.i18n.t('dataProviderType.dataSourceContext')
  }

  getDataChunk(applicationContext, path) {
    const [dataSourceId, ...rest] = path

    const pages = [
      applicationContext.page,
      this.app.store.getters['page/getSharedPage'](applicationContext.builder),
    ]

    const dataSource = this.app.store.getters[
      'dataSource/getPagesDataSourceById'
    ](pages, parseInt(dataSourceId))

    return getValueAtPath(dataSource.context_data, rest.join('.'))
  }

  getDataContent(applicationContext) {
    const pages = [
      applicationContext.page,
      this.app.store.getters['page/getSharedPage'](applicationContext.builder),
    ]

    const dataSources =
      this.app.store.getters['dataSource/getPagesDataSources'](pages)

    return Object.fromEntries(
      dataSources.map((dataSource) => [dataSource.id, dataSource.context_data])
    )
  }

  getDataSchema(applicationContext) {
    const pages = [
      this.app.store.getters['page/getSharedPage'](applicationContext.builder),
      applicationContext.page,
    ]

    const dataSources =
      this.app.store.getters['dataSource/getPagesDataSources'](pages)

    const contextDataSchema = Object.fromEntries(
      dataSources
        .filter((dataSource) => dataSource?.type)
        .map((dataSource, index) => {
          const dsSchema = this.app.$registry
            .get('service', dataSource.type)
            .getContextDataSchema(dataSource)

          if (dsSchema) {
            dsSchema.order = index
          }
          return [dataSource.id, dsSchema]
        })
        .filter(([, schema]) => schema)
    )

    return { type: 'object', properties: contextDataSchema }
  }

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 2) {
      const pages = [
        applicationContext.page,
        this.app.store.getters['page/getSharedPage'](
          applicationContext.builder
        ),
      ]
      const dataSourceId = parseInt(pathParts[1])
      return (
        this.app.store.getters['dataSource/getPagesDataSourceById'](
          pages,
          dataSourceId
        )?.name || `data_source_context_${dataSourceId}`
      )
    }
    return super.getPathTitle(applicationContext, pathParts)
  }
}

export class PageParameterDataProviderType extends DataProviderType {
  static getType() {
    return 'page_parameter'
  }

  get name() {
    return this.app.i18n.t('dataProviderType.pageParameter')
  }

  async init(applicationContext) {
    const { page, mode, pageParamsValue } = applicationContext
    const pageParams = [...page.path_params, ...page.query_params]

    // Read parameters value from the application context
    const queryParamNames = page.query_params.map((p) => p.name)
    if (mode === 'editing') {
      // Generate fake values for the parameters
      await Promise.all(
        pageParams.map(({ name, type }) => {
          const isQuery = queryParamNames.includes(name)
          return this.app.store.dispatch('pageParameter/setParameter', {
            page,
            name,
            value: isQuery ? null : defaultValueForParameterType(type),
          })
        })
      )
    } else {
      await Promise.all(
        pageParams.map(({ name, type }) => {
          const validators = queryParamNames.includes(name)
            ? QUERY_PARAM_TYPE_HANDLER_FUNCTIONS
            : PAGE_PARAM_TYPE_VALIDATION_FUNCTIONS
          let value
          try {
            value = validators[type](pageParamsValue[name])
          } catch {
            // Skip setting the parameter if the user-provided value
            // doesn't pass our parameter `type` validation.
            return null
          }
          return this.app.store.dispatch('pageParameter/setParameter', {
            page,
            name,
            value,
          })
        })
      )
    }
  }

  getDataChunk(applicationContext, path) {
    const content = this.getDataContent(applicationContext)
    return getValueAtPath(content, path.join('.'))
  }

  getDataSourceDispatchContext(applicationContext) {
    return this.getDataContent(applicationContext)
  }

  getDataContent(applicationContext) {
    if (!applicationContext.page) {
      // It's probably called at application level
      return null
    }
    return this.app.store.getters['pageParameter/getParameters'](
      applicationContext.page
    )
  }

  getDataSchema(applicationContext) {
    const page = applicationContext.page
    const toJSONType = { text: 'string', numeric: 'number' }
    const mergedParams = [
      ...(page?.path_params || []),
      ...(page?.query_params || []),
    ]

    return {
      type: 'object',
      properties: Object.fromEntries(
        mergedParams.map(({ name, type }) => [
          name,
          {
            title: name,
            type: toJSONType[type],
          },
        ])
      ),
    }
  }
}

export class CurrentRecordDataProviderType extends DataProviderType {
  static getType() {
    return 'current_record'
  }

  get name() {
    return this.app.i18n.t('dataProviderType.currentRecord')
  }

  get indexKey() {
    // Prevent collision with user data
    return '__idx__'
  }

  get needBackendContext() {
    return true
  }

  getActionDispatchContext(applicationContext) {
    return {
      record_id: applicationContext.recordId,
      index: applicationContext.recordIndexPath.at(-1),
    }
  }

  getDataChunk(applicationContext, path) {
    const { element, recordIndexPath = [0] } = applicationContext

    const elementType = this.app.$registry.get('element', element.type)

    // Special case for the index
    if (path.length === 1 && path[0] === this.indexKey) {
      return recordIndexPath.at(-1)
    }

    return elementType.getElementCurrentContent(applicationContext, path)
  }

  getDataSourceSchema(dataSource) {
    if (dataSource?.type) {
      const serviceType = this.app.$registry.get('service', dataSource.type)
      return serviceType.getDataSchema(dataSource)
    }
    return null
  }

  /**
   * Given a data source's schema, is responsible for returning the properties.
   * Depending on the schema's `type`, it will be in different places.
   * @param {object} schema - the data source's schema.
   * @returns {object} - the schema's properties.
   */
  getDataSourceSchemaProperties(schema) {
    return schema.type === 'array'
      ? schema?.items?.properties
      : schema.properties
  }

  getDataSourceAndSchemaPath(
    builder,
    page,
    element,
    allowSameElement,
    followSameElementSchemaProperties
  ) {
    const pages = [page, this.app.store.getters['page/getSharedPage'](builder)]

    const elementType = this.app.$registry.get('element', element.type)

    // Find the first collection ancestor with a `data_source`. If we
    // find one, this is what we'll use to generate the schema.
    const collectionAncestors = elementType.getCollectionAncestry({
      page,
      element,
      allowSameElement,
    })

    if (collectionAncestors.length === 0) {
      // No collection ancestor with a valid data_source_id we can break now.
      return [null, null]
    }

    const firstCollectionElement = collectionAncestors[0]
    const dataSourceId = firstCollectionElement.data_source_id

    const dataSource = this.app.store.getters[
      'dataSource/getPagesDataSourceById'
    ](pages, dataSourceId)

    const schemaProperties = collectionAncestors
      .filter(
        (ancestor) =>
          ancestor.schema_property &&
          (followSameElementSchemaProperties || ancestor.id !== element.id)
      )
      .map(({ schema_property: schemaProperty }) => schemaProperty)

    return [dataSource, schemaProperties]
  }

  getDataSchema(applicationContext) {
    // `allowSameElement` is set if we want to consider the current element in the
    // collection ancestry list. If so it will be used to get the data source id if
    // it's the first collection element.
    // `followSameElementSchemaProperties` can be passed in the `applicationContext`
    // to control whether we wish to fetch schema property for the current element
    // or not.
    const {
      builder,
      page,
      element,
      allowSameElement = false,
      followSameElementSchemaProperties = true,
    } = applicationContext

    const [dataSource, schemaProperties] = this.getDataSourceAndSchemaPath(
      builder,
      page,
      element,
      allowSameElement,
      followSameElementSchemaProperties
    )

    if (dataSource === null) {
      return null
    }

    // Extract the subSchema corresponding to the schemaProperties path.
    const schema = this.getDataSourceSchema(dataSource)
    const subSchema = extractSubSchema(schema, schemaProperties)

    if (subSchema === null) {
      return null
    }

    // Here we add the index property schema
    const properties = {
      [this.indexKey]: {
        type: 'number',
        title: this.app.i18n.t('currentRecordDataProviderType.index'),
        sortable: false,
        filterable: false,
        searchable: false,
      },
      ...this.getDataSourceSchemaProperties(subSchema),
    }

    return { type: 'object', properties }
  }

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 1) {
      const {
        builder,
        page,
        element,
        allowSameElement = false,
        followSameElementSchemaProperties = true,
      } = applicationContext

      const [dataSource, schemaProperties] = this.getDataSourceAndSchemaPath(
        builder,
        page,
        element,
        allowSameElement,
        followSameElementSchemaProperties
      )

      // We have no data source. Let's just return the part.
      if (!dataSource) {
        return pathParts[0]
      }

      // If we have at least an ancestor with a schema property,
      // we'll find the title using this property.
      if (schemaProperties.length > 0) {
        const schema = this.getDataSourceSchema(dataSource)
        const schemaField = extractSubSchema(schema, schemaProperties)

        if (schemaField === null) {
          // The dataSource has probably changed and the schemaProperties are
          // not valid anymore.
          return pathParts[0]
        }

        let prefixName = dataSource.name
        // Only Local/Remote Baserow table schemas will have `original_type`,
        // which is the `FieldType`. If we find it, we can use it to display
        // what kind of field type was used.
        if (schemaField.original_type) {
          const fieldType = this.app.$registry.get(
            'field',
            schemaField.original_type
          )
          prefixName = fieldType.getName()
        }
        const propertyTitle = schemaField.title
        return this.app.i18n.t('currentRecordDataProviderType.schemaProperty', {
          prefixName,
          schemaProperty: propertyTitle,
        })
      }

      return this.app.i18n.t('currentRecordDataProviderType.firstPartName', {
        name: dataSource.name,
      })
    }

    return super.getPathTitle(applicationContext, pathParts)
  }
}

export class FormDataProviderType extends DataProviderType {
  static getType() {
    return 'form_data'
  }

  get name() {
    return this.app.i18n.t('dataProviderType.formData')
  }

  getActionDispatchContext(applicationContext) {
    const { page } = applicationContext
    const dataContent = this.getDataContent(applicationContext)

    const files = {}

    const updatedValue = Object.fromEntries(
      Object.entries(dataContent)
        .filter(([elementId, value]) => {
          const element = this.app.store.getters['element/getElementById'](
            page,
            elementId
          )
          const elementType = this.app.$registry.get('element', element.type)
          return !elementType.isDeactivated({
            workspace: applicationContext.workspace,
          })
        })
        .map(([elementId, value]) => {
          const element = this.app.store.getters['element/getElementById'](
            page,
            elementId
          )
          const elementType = this.app.$registry.get('element', element.type)

          return [
            elementId,
            elementType.beforeActionDispatchContext(element, value, files),
          ]
        })
    )

    return [updatedValue, files]
  }

  /**
   * Responsible for filtering down an array of page elements to only those that
   * are form elements, and are in the same 'element namespace path' as one another.
   * For example:
   *
   * - HeadingRoot (path=[])
   *     * Can access `InputRoot`
   *     * Can access `InputContainer`
   * - InputRoot (path=[])
   * - FormContainer (path=[])
   *     - InputContainer (path=[])
   * - RepeatA (path=[])
   *     - InputOuter (path=[RepeatA.id])
   *     - HeadingOuter (path=[RepeatA.id])
   *         * Can access `InputOuter`
   *         * Can access `InputRoot`
   *         * Can access `InputContainer`
   *     - RepeatB (path=[RepeatA.id])
   *        - InputInner (path=[RepeatA.id, RepeatB.id])
   *        - HeadingInner (path=[RepeatA.id, RepeatB.id])
   *            * Can access `InputInner`
   *            * Can access `InputOuter`
   *            * Can access `InputRoot`
   *            * Can access `InputContainer`
   *
   * @param {Object} applicationContext - The application context object.
   * @param {Object} targetElement - The target element object.
   * @returns {Array} The filtered array of form elements in the same namespace as the target.
   */
  formElementsInNamespacePath(applicationContext, targetElement) {
    const { page } = applicationContext

    const targetNamespacePath =
      this.app.store.getters['element/getElementNamespacePath'](
        targetElement
      ).join('.')

    const elements = this.app.store.getters['element/getElementsOrdered'](page)
    return elements.filter((element) => {
      const elementType = this.app.$registry.get('element', element.type)
      if (!elementType.isFormElement) {
        // We only want to find accessible *form elements*.
        return false
      }
      const elementNamespacePath =
        this.app.store.getters['element/getElementNamespacePath'](element).join(
          '.'
        )

      return targetNamespacePath.startsWith(elementNamespacePath)
    })
  }

  getDataChunk(applicationContext, path) {
    const content = this.getDataContent(applicationContext)
    return getValueAtPath(content, path.join('.'))
  }

  getDataContent(applicationContext) {
    const { element: targetElement } = applicationContext
    const formData = this.app.store.getters['formData/getFormData'](
      applicationContext.page
    )

    const accessibleFormElements = this.formElementsInNamespacePath(
      applicationContext,
      targetElement
    )

    return Object.fromEntries(
      accessibleFormElements.map((element) => {
        const uniqueElementId = this.app.$registry
          .get('element', element.type)
          .uniqueElementId({ element, applicationContext })

        const formEntry = getValueAtPath(formData, uniqueElementId)
        return [element.id, formEntry?.value]
      })
    )
  }

  getDataSchema(applicationContext) {
    const { page, element: targetElement } = applicationContext
    const accessibleFormElements = this.formElementsInNamespacePath(
      applicationContext,
      targetElement
    )
    return {
      type: 'object',
      properties: Object.fromEntries(
        accessibleFormElements.map((element) => {
          const elementType = this.app.$registry.get('element', element.type)
          const name = elementType.getDisplayName(element, applicationContext)
          const order = this.app.store.getters['element/getElementPosition'](
            page,
            element
          )
          return [
            element.id,
            {
              title: name,
              order,
              ...elementType.getDataSchema(element),
            },
          ]
        })
      ),
    }
  }

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 2) {
      const elementId = parseInt(pathParts[1], 10)

      const element = this.app.store.getters['element/getElementById'](
        applicationContext.page,
        parseInt(elementId)
      )
      if (!element) {
        return this.app.i18n.t('formDataProviderType.nodeMissing')
      }
    }

    return super.getPathTitle(applicationContext, pathParts)
  }
}

export class PreviousActionDataProviderType extends DataProviderType {
  static getType() {
    return 'previous_action'
  }

  get name() {
    return this.app.i18n.t('dataProviderType.previousAction')
  }

  get needBackendContext() {
    return true
  }

  getActionDispatchContext(applicationContext) {
    return {
      ...this.getDataContent(applicationContext),
      current_dispatch_id: applicationContext.currentDispatchId,
    }
  }

  getDataChunk(applicationContext, path) {
    const content = this.getDataContent(applicationContext)

    const [workflowActionId, ...rest] = path

    const workflowAction = this.app.store.getters[
      'builderWorkflowAction/getWorkflowActionById'
    ](applicationContext.page, parseInt(workflowActionId))

    const actionType = this.app.$registry.get(
      'workflowAction',
      workflowAction.type
    )

    if (!content[workflowActionId]) {
      return null
    }

    return getValueAtPath(
      content[workflowActionId],
      actionType.prepareValuePath(workflowAction, rest)
    )
  }

  getWorkflowActionSchema(workflowAction) {
    if (workflowAction?.type) {
      const actionType = this.app.$registry.get(
        'workflowAction',
        workflowAction.type
      )
      return actionType.getDataSchema(workflowAction)
    }
    return null
  }

  getDataContent(applicationContext) {
    return applicationContext.previousActionResults
  }

  getDataSchema(applicationContext) {
    const page = applicationContext.page

    const previousActions = this.app.store.getters[
      'builderWorkflowAction/getElementPreviousWorkflowActions'
    ](page, applicationContext.element.id, applicationContext.workflowAction)

    const previousActionSchema = _.chain(previousActions)
      // Retrieve the associated schema for each action
      .map((workflowAction) => [
        workflowAction,
        this.getWorkflowActionSchema(workflowAction),
      ])
      // Remove actions without schema
      .filter(([_, schema]) => schema)
      // Add an index number to the schema title for each workflow action of
      // the same type.
      // For example if we have 2 update and create row actions we want their
      // titles to be: [Update row,  Create row, Update row 2, Create row 2]
      .groupBy('0.type')
      .flatMap((workflowActions) =>
        workflowActions.map(([workflowAction, schema], index) => [
          workflowAction.id,
          { ...schema, title: `${schema.title} ${index ? index + 1 : ''}` },
        ])
      )
      // Create the schema object
      .fromPairs()
      .value()
    return { type: 'object', properties: previousActionSchema }
  }

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 2) {
      const page = applicationContext?.page
      const workflowActionId = parseInt(pathParts[1])

      const action = this.app.store.getters[
        'builderWorkflowAction/getWorkflowActionById'
      ](page, workflowActionId)

      if (!action) {
        return `action_${workflowActionId}`
      }
    }
    return super.getPathTitle(applicationContext, pathParts)
  }
}

export class UserDataProviderType extends DataProviderType {
  static getType() {
    return 'user'
  }

  get name() {
    return this.app.i18n.t('dataProviderType.user')
  }

  getDataSourceDispatchContext(applicationContext) {
    const { is_authenticated: isAuthenticated, id } =
      this.getDataContent(applicationContext)

    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone

    if (isAuthenticated) {
      return {
        id,
        timezone,
      }
    } else {
      return {
        id: null,
        timezone,
      }
    }
  }

  getDataChunk(applicationContext, path) {
    const content = this.getDataContent(applicationContext)
    return getValueAtPath(content, path.join('.'))
  }

  getDataContent({ builder }) {
    const loggedUser = this.app.store.getters['userSourceUser/getUser'](builder)

    const context = {
      is_authenticated:
        this.app.store.getters['userSourceUser/isAuthenticated'](builder),
      ...loggedUser,
    }

    if (context.role?.startsWith(DEFAULT_USER_ROLE_PREFIX)) {
      const userSource = this.app.store.getters[
        'userSource/getUserSourceByUId'
      ](builder, loggedUser.user_source_uid)

      if (userSource) {
        context.role = this.app.i18n.t('visibilityForm.rolesAllMembersOf', {
          name: userSource.name,
        })
      }
    }

    return context
  }

  getDataSchema(applicationContext) {
    return {
      type: 'object',
      properties: {
        is_authenticated: {
          title: this.app.i18n.t('userDataProviderType.isAuthenticated'),
          type: 'boolean',
        },
        id: {
          type: 'number',
          title: this.app.i18n.t('userDataProviderType.id'),
        },
        email: {
          type: 'string',
          title: this.app.i18n.t('userDataProviderType.email'),
        },
        username: {
          type: 'string',
          title: this.app.i18n.t('userDataProviderType.username'),
        },
        role: {
          type: 'string',
          title: this.app.i18n.t('userDataProviderType.role'),
        },
      },
    }
  }
}
