import { computed, unref } from 'vue'
import { warn } from '../utils'
import { useVueFlow } from './useVueFlow'

/**
 * Composable for receiving data of one or multiple nodes
 *
 * @public
 * @param nodeId - The id (or ids) of the node to get the data from
 * @param guard - Optional guard function to narrow down the node type
 * @returns An array of data objects
 */
export function useNodesData(_nodeIds) {
  const { findNode } = useVueFlow({})

  return computed({
    get() {
      const nodeIds = unref(_nodeIds)

      if (!Array.isArray(nodeIds)) {
        const node = findNode(nodeIds)

        if (node) {
          return {
            id: node.id,
            type: node.type,
            data: node.data,
          }
        }

        return null
      }

      const data = []

      for (const nodeId of nodeIds) {
        const node = findNode(nodeId)

        if (node) {
          data.push({
            id: node.id,
            type: node.type,
            data: node.data,
          })
        }
      }

      return data
    },
    set() {
      // noop
      warn(
        'You are trying to set node data via useNodesData. This is not supported.'
      )
    },
  })
}
