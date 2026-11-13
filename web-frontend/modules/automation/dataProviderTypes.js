import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import _ from 'lodash'
import { getValueAtPath } from '@baserow/modules/core/utils/object'

// Tells a path the sample data doesn't hold apart from one holding `null`.
const NO_SAMPLE_VALUE = Symbol('noSampleValue')

/**
 * Returns the node with the given id in the workflow of the application
 * context, with its type, or `null` when there is no such node.
 */
const findNodeAndType = (app, applicationContext, nodeId) => {
  const node = app.$store.getters['automationWorkflowNode/findById'](
    applicationContext?.workflow,
    parseInt(nodeId)
  )
  if (!node?.type) {
    return null
  }
  return { node, nodeType: app.$registry.get('node', node.type) }
}

export class PreviousNodeDataProviderType extends DataProviderType {
  static getType() {
    return 'previous_node'
  }

  get name() {
    return this.app.$i18n.t('dataProviderType.previousNode')
  }

  getNodeSchema({ automation, node }) {
    if (node?.type) {
      const nodeType = this.app.$registry.get('node', node.type)
      return nodeType.getDataSchema({ automation, node })
    }
    return null
  }

  getDataSchema(applicationContext) {
    const { automation, workflow, node: currentNode } = applicationContext

    const previousNodes = this.app.$store.getters[
      'automationWorkflowNode/getPreviousNodes'
    ](workflow, currentNode, {
      predicate: (referenceNode, position, output) => position !== 'child',
    })

    const previousNodeSchema = _.chain(previousNodes)
      // Retrieve the associated schema for each node
      .map((previousNode, index) => [
        previousNode,
        this.getNodeSchema({ automation, node: previousNode }),
      ])
      // Remove nodes without schema
      .filter(([_, schema]) => schema)
      .map(([previousNode, schema], index) => [
        previousNode,
        { ...schema, order: index },
      ])
      // Add an index number to the schema title for each node of the same
      // schema title. For example if we have two "Create a row in Customers"
      // nodes, then the schema titles will be:
      // [Create a row in Customers,  Create a row in Customers 2]
      .groupBy('1.title')
      .flatMap((previousNodes) =>
        previousNodes.map(([previousNode, schema], index) => [
          previousNode.id,
          {
            ...schema,
            title: `${schema.title}${index ? ` ${index + 1}` : ''}`,
          },
        ])
      )
      // Create the schema object
      .fromPairs()
      .value()

    return { type: 'object', properties: previousNodeSchema }
  }

  /**
   * Adds a hint to the previous nodes that have no values to show, because
   * they haven't been tested yet or their last test failed.
   */
  getNodes(applicationContext) {
    const providerNode = super.getNodes(applicationContext)
    if (!providerNode.nodes) {
      return providerNode
    }
    return {
      ...providerNode,
      nodes: providerNode.nodes.map((node) => {
        const found = findNodeAndType(
          this.app,
          applicationContext,
          node.identifier
        )
        if (!found || found.nodeType.hasSampleValues(found.node)) {
          return node
        }
        return {
          ...node,
          hint: this.app.$i18n.t('dataProviderType.testToSeeValues'),
        }
      }),
    }
  }

  /**
   * The value the previous node returned the last time it was tested. It's an
   * example shown next to the node's data in the explorer, `undefined` when
   * the node has not been tested.
   */
  getSampleValue(applicationContext, [nodeId, ...rest]) {
    if (rest.length === 0) {
      // The node itself is a heading in the explorer, not a value.
      return undefined
    }
    const found = findNodeAndType(this.app, applicationContext, nodeId)
    if (!found) {
      return undefined
    }
    return found.nodeType.getSampleValue(found.node, rest)
  }

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 2) {
      const workflow = applicationContext?.workflow
      const nodeId = parseInt(pathParts[1])

      const node = this.app.$store.getters['automationWorkflowNode/findById'](
        workflow,
        nodeId
      )

      if (!node) {
        return `node_${nodeId}`
      }
    }
    return super.getPathTitle(applicationContext, pathParts)
  }
}

export class CurrentIterationDataProviderType extends DataProviderType {
  static getType() {
    return 'current_iteration'
  }

  get name() {
    return this.app.$i18n.t('dataProviderType.currentIteration')
  }

  getNodeSchema({ automation, node }) {
    if (node?.type) {
      const nodeType = this.app.$registry.get('node', node.type)
      return nodeType.getDataSchema({ automation, node })
    }
    return null
  }

  getDataSchema(applicationContext) {
    const { automation, workflow, node: currentNode } = applicationContext

    const ancestors = this.app.$store.getters[
      'automationWorkflowNode/getAncestors'
    ](workflow, currentNode)

    const ancestorsSchema = _.chain(ancestors)
      // Retrieve the associated schema for each node
      .map((ancestor, index) => {
        const schema = this.getNodeSchema({ automation, node: ancestor })
        if (!schema) {
          return [ancestor, null]
        }
        return [
          ancestor,
          {
            title: schema.title,
            order: index,
            type: 'object',
            properties: {
              item: {
                ...schema.items,
                title: this.app.$i18n.t('dataProviderType.item'),
              },
              index: { type: 'number', title: 'index' },
            },
          },
        ]
      })
      // Remove nodes without schema
      .filter(([_, schema]) => schema)
      // Add an index number to the schema title for each node of the same
      // schema title. For example if we have two "Create a row in Customers"
      // nodes, then the schema titles will be:
      // [Create a row in Customers,  Create a row in Customers 2]
      .groupBy('1.title')
      .flatMap((ancestors) =>
        ancestors.map(([previousNode, schema], index) => [
          previousNode.id,
          { ...schema, title: `${schema.title} ${index ? index + 1 : ''}` },
        ])
      )
      // Create the schema object
      .fromPairs()
      .value()
    return { type: 'object', properties: ancestorsSchema }
  }

  /**
   * An example of the current iteration: the first item the parent node
   * returned the last time it was tested.
   */
  getSampleValue(applicationContext, [parentNodeId, ...rest]) {
    if (rest.length === 0) {
      return undefined
    }
    const found = findNodeAndType(this.app, applicationContext, parentNodeId)
    if (!found) {
      return undefined
    }
    const item = found.nodeType.getSampleValue(found.node, ['0'])
    if (item === undefined) {
      return undefined
    }
    try {
      const value = getValueAtPath({ index: 0, item }, rest, NO_SAMPLE_VALUE)
      return value === NO_SAMPLE_VALUE ? undefined : value
    } catch {
      return undefined
    }
  }

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 2) {
      const workflow = applicationContext?.workflow
      const nodeId = parseInt(pathParts[1])

      const node = this.app.$store.getters['automationWorkflowNode/findById'](
        workflow,
        nodeId
      )

      if (!node) {
        return `node_${nodeId}`
      }
    }
    return super.getPathTitle(applicationContext, pathParts)
  }
}

/**
 * The result of the node being edited. The backend only exposes it while it
 * evaluates that node's retry condition, so this provider is offered to the
 * retry condition input alone (see `DATA_PROVIDERS_ALLOWED_RETRY_CONDITION`).
 * There is no node id in the path: `current_node.status_code` reads the
 * `status_code` of the node's own result.
 */
export class CurrentNodeDataProviderType extends DataProviderType {
  static getType() {
    return 'current_node'
  }

  get name() {
    return this.app.$i18n.t('dataProviderType.currentNode')
  }

  getDataSchema(applicationContext) {
    const { automation, node } = applicationContext
    if (!node?.type) {
      return null
    }
    const nodeType = this.app.$registry.get('node', node.type)
    const schema = nodeType.getDataSchema({ automation, node })
    return schema ? { ...schema, title: this.name } : null
  }

  /**
   * The value the edited node returned the last time it was tested.
   */
  getSampleValue(applicationContext, path) {
    const { node } = applicationContext
    if (!node?.type) {
      return undefined
    }
    return this.app.$registry.get('node', node.type).getSampleValue(node, path)
  }
}
