import { Registerable } from '@baserow/modules/core/registry'
import { getIconForType } from '@baserow/modules/core/utils/icon'

/**
 * A data provider gets data from the application context and populate the context for
 * the formula resolver.
 */
export class DataProviderType extends Registerable {
  get name() {
    throw new Error('`name` must be set on the dataProviderType.')
  }

  /**
   * Should be true if the data provider needs backend context during its
   * initialisation phase.
   */
  get needBackendContext() {
    return false
  }

  /**
   * Initialize the data needed by the data provider for the current application.
   * Used during the application init phase to collect all the data for the first
   * display.
   */
  async initOnce(r) {}

  /**
   * Initialize the data needed by the data provider for the current page.
   * Used during the page init phase to collect all the data for the first display.
   */
  async init(r) {}

  /**
   * Call init Once step of all given data providers according to the application
   * context
   * @param {Array} dataProviders
   * @param {Object} applicationContext the application context.
   */
  static async initOnceAll(dataProviders, applicationContext) {
    // First we initialize providers that doesn't need a backend context
    await Promise.all(
      Object.values(dataProviders)
        .filter((provider) => !provider.needBackendContext)
        .map((dataProvider) => dataProvider.initOnce(applicationContext))
    )
    // Then we initialize those that need the backend context
    await Promise.all(
      Object.values(dataProviders)
        .filter((provider) => provider.needBackendContext)
        .map((dataProvider) => dataProvider.initOnce(applicationContext))
    )
  }

  /**
   * Call init step of all given data providers according to the application context
   * @param {Array} dataProviders
   * @param {Object} applicationContext the application context.
   */
  static async initAll(dataProviders, applicationContext) {
    // First we initialize providers that doesn't need a backend context
    await Promise.all(
      Object.values(dataProviders)
        .filter((provider) => !provider.needBackendContext)
        .map((dataProvider) => dataProvider.init(applicationContext))
    )
    // Then we initialize those that need the backend context
    await Promise.all(
      Object.values(dataProviders)
        .filter((provider) => provider.needBackendContext)
        .map((dataProvider) => dataProvider.init(applicationContext))
    )
  }

  static getAllActionDispatchContext(dataProviders, applicationContext) {
    return Object.fromEntries(
      Object.values(dataProviders).map((dataProvider) => {
        return [
          dataProvider.type,
          dataProvider.getActionDispatchContext(applicationContext),
        ]
      })
    )
  }

  static getAllDataSourceDispatchContext(dataProviders, applicationContext) {
    return Object.fromEntries(
      Object.values(dataProviders).map((dataProvider) => {
        return [
          dataProvider.type,
          dataProvider.getDataSourceDispatchContext(applicationContext),
        ]
      })
    )
  }

  /**
   * Should return the context needed to be sent to the backend for each dataProvider
   * to be able to solve the formulas on the backend.
   * @param {Object} applicationContext the application context.
   * @returns An object if the dataProvider wants to send something to the backend.
   */
  getDataSourceDispatchContext(applicationContext) {
    return null
  }

  getActionDispatchContext(applicationContext) {
    return this.getDataSourceDispatchContext(applicationContext)
  }

  /**
   * Returns the actual data for the given path.
   * @param {object} applicationContext the application context.
   * @param {Array<str>} path the path of the data we want to get
   */
  getDataChunk(applicationContext, path) {
    throw new Error('.getDataChunk() must be set on the dataProviderType.')
  }

  /**
   * Return the data content for this data provider.
   * @param {Object} applicationContext the application context.
   * @returns {{$schema: string}}
   */
  getDataContent(applicationContext) {
    throw new Error('.getDataContent() must be set on the dataProviderType.')
  }

  /**
   * Return the schema of the data provided by this data provider
   * @param {Object} applicationContext the application context.
   * @returns {{type: string, properties: object}}
   */
  getDataSchema(applicationContext) {
    throw new Error('.getDataSchema() must be set on the dataProviderType.')
  }

  /**
   * Return the schema of the context data provided by this data provider
   * @param {Object} applicationContext the application context.
   * @returns {{type: string, properties: object}}
   */
  getContextDataSchema(applicationContext) {
    throw new Error(
      '.getContextDataSchema() must be set on the dataProviderType.'
    )
  }

  /**
   * This function returns an object that can be read by the data explorer to display
   * the data available from each data provider.
   *
   * Make sure to implement `getDataContent`, `getDataSchema` and `getContextDataSchema`
   * for every data provider if they should show data in the data explorer.
   *
   * @param {Object} applicationContext the application context.
   * @returns {{identifier: string, name: string, nodes: []}}
   */
  getNodes(applicationContext) {
    const schema = this.getDataSchema(applicationContext)
    if (schema === null) {
      return {}
    }
    return this._toNode(applicationContext, [this.type], schema)
  }

  /**
   * Recursive method to deeply compute the node tree for this data providers.
   * @param {Object} applicationContext the application context.
   * @param {Array<String>} pathParts the path to get to the current node.
   * @param {$schema: string} schema the current node schema.
   * @returns {{identifier: string, name: string, nodes: []}}
   */
  _toNode(applicationContext, pathParts, schema) {
    const identifier = pathParts.at(-1)
    const name = this.getPathTitle(applicationContext, pathParts)
    const order = schema?.order ?? null

    if (schema === null) {
      return {
        name,
        order,
        type: null,
        icon: this.getIconForNode(null),
        identifier,
      }
    }

    if (schema.anyOf) {
      const schemaObject = schema.anyOf.find((s) => s.type === 'object')

      return {
        name,
        identifier,
        order,
        type: 'union',
        icon: this.getIconForNode({ type: 'union' }),
        nodes: [
          // Always allow direct access to the entire value
          {
            name: `${name} (${this.app.i18n.t('common.value')})`,
            identifier: '',
            order: 0,
            type: 'unknown',
            icon: this.getIconForNode({ type: 'union' }),
          },

          // If it is an object, show the individual properties
          ...(schemaObject && schemaObject.properties
            ? Object.entries(schemaObject.properties).map(([key, subSchema]) =>
                this._toNode(applicationContext, [...pathParts, key], subSchema)
              )
            : []),
        ],
      }
    }

    if (schema.type === 'array') {
      return {
        name,
        identifier,
        order,
        icon: this.getIconForNode(schema),
        type: 'array',
        nodes: schema.items
          ? this._toNode(applicationContext, [...pathParts, null], schema.items)
              .nodes
          : [],
      }
    }

    if (schema.type === 'object') {
      return {
        name,
        identifier,
        order,
        icon: this.getIconForNode(schema),
        nodes: schema.properties
          ? Object.entries(schema.properties).map(([identifier, subSchema]) =>
              this._toNode(
                applicationContext,
                [...pathParts, identifier],
                subSchema
              )
            )
          : [],
      }
    }

    return {
      name,
      order,
      type: schema.type,
      icon: this.getIconForNode(schema),
      identifier,
    }
  }

  /**
   * This function gives you the icon that can be used by the data explorer given
   * the type of the data. It allows to customize the way type icons are selected.
   * @param type - The type of the data
   * @returns {*|string} - The corresponding icon
   */
  getIconForNode(schema) {
    if (schema) {
      return getIconForType(schema.type)
    } else {
      return getIconForType(null)
    }
  }

  /**
   * Returns the schema matching the given path
   * @param {Object} schemaNode
   * @param {Array<String>} pathParts
   * @returns the schema at the given path.
   */
  getSchemaNode(schemaNode, pathParts) {
    if (pathParts.length === 0) {
      return schemaNode
    }

    if (!schemaNode) {
      return null
    }

    const [first, ...rest] = pathParts

    if (schemaNode.type === 'array') {
      const nodeSchema = this.getSchemaNode(schemaNode.items, rest)

      if (pathParts.at(-1) === '*') {
        return { ...nodeSchema, title: `[${this.app.i18n.t('common.all')}]` }
      }

      return nodeSchema
    }

    if (schemaNode.type === 'object') {
      const properties = schemaNode.properties || {}
      return this.getSchemaNode(properties[first], rest)
    }
  }

  /**
   * This function lets you hook into the path translation. Sometimes the path uses an
   * ID to reference an item, but we want to show the name of the item to the user
   * instead.
   * @param {Object} applicationContext the application context.
   * @param {Array<string>} pathParts - the path
   * @returns {Array<String>} - modified path part as it should be displayed to the user
   */
  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 1) {
      return this.name
    }

    const [, ...rest] = pathParts

    const schema = this.getDataSchema(applicationContext)
    const schemaNode = this.getSchemaNode(schema, rest)

    return schemaNode?.title ? schemaNode.title : pathParts.at(-1)
  }

  getOrder() {
    return 0
  }
}
