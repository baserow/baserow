import { computed, ref, toRef, unref, watch } from 'vue'
import { areConnectionMapsEqual, handleConnectionChange } from '../utils'
import { useNodeId } from './useNodeId'
import { useVueFlow } from './useVueFlow'

/**
 * Composable that returns existing connections of a `<Handle />`.
 *
 * @deprecated use `useNodeConnections` instead
 * @public
 * @param params
 * @param params.type - handle type `source` or `target`
 * @param params.nodeId - node id - if not provided, the node id from the `useNodeId` (meaning, the context-based injection) is used
 * @param params.id - the handle id (this is required if the node has multiple handles of the same type)
 * @param params.onConnect - gets called when a connection is created
 * @param params.onDisconnect - gets called when a connection is removed
 *
 * @returns An array of connections
 */
export function useHandleConnections(params) {
  const { type, id, nodeId, onConnect, onDisconnect } = params

  const { connectionLookup } = useVueFlow({})

  const _nodeId = useNodeId()

  const currentNodeId = toRef(() => unref(nodeId) ?? _nodeId)

  const handleType = toRef(() => unref(type))

  const handleId = toRef(() => unref(id) ?? null)

  const prevConnections = ref(null)

  const connections = ref()

  watch(
    () =>
      connectionLookup.value.get(
        `${currentNodeId.value}-${handleType.value}-${handleId.value}`
      ),
    (nextConnections) => {
      if (areConnectionMapsEqual(connections.value, nextConnections)) {
        return
      }

      connections.value = nextConnections
    },
    { immediate: true }
  )

  watch(
    [
      connections,
      () => typeof onConnect !== 'undefined',
      () => typeof onDisconnect !== 'undefined',
    ],
    ([currentConnections = new Map()]) => {
      if (
        prevConnections.value &&
        prevConnections.value !== currentConnections
      ) {
        handleConnectionChange(
          prevConnections.value,
          currentConnections,
          onDisconnect
        )
        handleConnectionChange(
          currentConnections,
          prevConnections.value,
          onConnect
        )
      }

      prevConnections.value = currentConnections
    },
    { immediate: true }
  )

  return computed(() => {
    if (!connections.value) {
      return []
    }

    return Array.from(connections.value.values())
  })
}
