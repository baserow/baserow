import { computed, unref } from 'vue'
import { warn } from '../utils'
import { useVueFlow } from './useVueFlow'

/**
 * Composable for receiving data of one or multiple nodes
 *
 * @public
 * @param edgeId - The id (or ids) of the node to get the data from
 * @returns An array of data objects or a single data object
 */
export function useEdgesData(_edgeIds) {
  const { findEdge } = useVueFlow({})

  return computed({
    get() {
      const edgeIds = unref(_edgeIds)

      if (!Array.isArray(edgeIds)) {
        const edge = findEdge(edgeIds)

        if (edge) {
          return {
            id: edge.id,
            type: edge.type,
            data: edge.data ?? null,
          }
        }

        return null
      }

      const data = []

      for (const edgeId of edgeIds) {
        const edge = findEdge(edgeId)

        if (edge) {
          data.push({
            id: edge.id,
            type: edge.type,
            data: edge.data ?? null,
          })
        }
      }

      return data
    },
    set() {
      // noop
      warn(
        'You are trying to set edge data via useEdgesData. This is not supported.'
      )
    },
  })
}
