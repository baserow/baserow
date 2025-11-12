import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import _ from 'lodash'

export class PreviousNodeDataProviderType extends DataProviderType {
  static getType() {
    return 'previous_node'
  }

  get name() {
    return this.app.i18n.t('dataProviderType.previousNode')
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

    const previousNodes = this.app.store.getters[
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

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 2) {
      const workflow = applicationContext?.workflow
      const nodeId = parseInt(pathParts[1])

      const node = this.app.store.getters['automationWorkflowNode/findById'](
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
    return this.app.i18n.t('dataProviderType.currentIteration')
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

    const ancestors = this.app.store.getters[
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
                title: this.app.i18n.t('dataProviderType.item'),
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

  getPathTitle(applicationContext, pathParts) {
    if (pathParts.length === 2) {
      const workflow = applicationContext?.workflow
      const nodeId = parseInt(pathParts[1])

      const node = this.app.store.getters['automationWorkflowNode/findById'](
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
