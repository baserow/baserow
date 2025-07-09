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

    // TODO: currently finds nodes "before" the current node in the workflow
    //  exclusively using the `order` property. This will require more nuance
    //  in the future, as we might want to consider other factors.
    const previousNodes = this.app.store.getters[
      'automationWorkflowNode/getNodesOrdered'
    ](workflow).filter((node) => node.order < currentNode.order)

    const previousNodeSchema = _.chain(previousNodes)
      // Retrieve the associated schema for each node
      .map((previousNode) => [
        previousNode,
        this.getNodeSchema({ automation, node: previousNode }),
      ])
      // Remove nodes without schema
      .filter(([_, schema]) => schema)
      // Add an index number to the schema title for each node of the same type.
      // For example if we have 2 update and create row nodes we want their
      // titles to be: [Update row,  Create row, Update row 2, Create row 2]
      .groupBy('0.type')
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
