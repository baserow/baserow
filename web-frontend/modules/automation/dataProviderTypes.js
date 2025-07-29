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
    ](workflow, currentNode)

    const previousNodeSchema = _.chain(previousNodes)
      // Retrieve the associated schema for each node
      .map((previousNode) => [
        previousNode,
        this.getNodeSchema({ automation, node: previousNode }),
      ])
      // Remove nodes without schema
      .filter(([_, schema]) => schema)
      // Add an index number to the schema title for each node of the same
      // schema title. For example if we have two "Create a row in Customers"
      // nodes, then the schema titles will be:
      // [Create a row in Customers,  Create a row in Customers 2]
      .groupBy('1.title')
      .flatMap((previousNodes) =>
        previousNodes.map(([previousNode, schema], index) => [
          previousNode.id,
          { ...schema, title: `${schema.title} ${index ? index + 1 : ''}` },
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
