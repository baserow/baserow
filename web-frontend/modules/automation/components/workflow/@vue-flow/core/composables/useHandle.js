import { unref } from 'vue'
import {
  calcAutoPan,
  getClosestHandle,
  getConnectionStatus,
  getEventPosition,
  getHandle,
  getHandlePosition,
  getHandleType,
  getHostForElement,
  isConnectionValid,
  isMouseEvent,
  isValidHandle,
  oppositePosition,
  pointToRendererPoint,
  rendererPointToPoint,
  resetRecentHandle,
} from '../utils'
import { useVueFlow } from './useVueFlow'

// Définition locale de l'énumération Position
const Position = {
  Left: 'left',
  Right: 'right',
  Top: 'top',
  Bottom: 'bottom',
}

function alwaysValid() {
  return true
}

/**
 * This composable provides listeners for handle events
 *
 * Generally it's recommended to use the `<Handle />` component instead of this composable.
 *
 * @public
 */
export function useHandle({
  handleId,
  nodeId,
  type,
  isValidConnection,
  edgeUpdaterType,
  onEdgeUpdate,
  onEdgeUpdateEnd,
}) {
  const {
    id: flowId,
    vueFlowRef,
    connectionMode,
    connectionRadius,
    connectOnClick,
    connectionClickStartHandle,
    nodesConnectable,
    autoPanOnConnect,
    autoPanSpeed,
    findNode,
    panBy,
    startConnection,
    updateConnection,
    endConnection,
    emits,
    viewport,
    edges,
    nodes,
    isValidConnection: isValidConnectionProp,
    nodeLookup,
  } = useVueFlow({})

  let connection = null
  let isValid = false
  let handleDomNode = null

  function handlePointerDown(event) {
    const isTarget = unref(type) === 'target'

    const isMouseTriggered = isMouseEvent(event)

    // when vue-flow is used inside a shadow root we can't use document
    const doc = getHostForElement(event.target)

    if ((isMouseTriggered && event.button === 0) || !isMouseTriggered) {
      const node = findNode(unref(nodeId))

      let isValidConnectionHandler =
        unref(isValidConnection) || isValidConnectionProp.value || alwaysValid

      if (!isValidConnectionHandler && node) {
        isValidConnectionHandler =
          (!isTarget ? node.isValidTargetPos : node.isValidSourcePos) ||
          alwaysValid
      }

      let closestHandle = null

      let autoPanId = 0

      const { x, y } = getEventPosition(event)
      const clickedHandle = doc?.elementFromPoint(x, y)
      const handleType = getHandleType(unref(edgeUpdaterType), clickedHandle)
      const containerBounds = vueFlowRef.value?.getBoundingClientRect()

      if (!containerBounds || !handleType) {
        return
      }

      const fromHandleInternal = getHandle(
        unref(nodeId),
        handleType,
        unref(handleId),
        nodeLookup.value,
        connectionMode.value
      )

      if (!fromHandleInternal) {
        return
      }

      let prevActiveHandle
      let connectionPosition = getEventPosition(event, containerBounds)
      let autoPanStarted = false

      // when the user is moving the mouse close to the edge of the canvas while connecting we move the canvas
      const autoPan = function () {
        if (!autoPanOnConnect.value) {
          return
        }

        const [xMovement, yMovement] = calcAutoPan(
          connectionPosition,
          containerBounds,
          autoPanSpeed.value
        )

        panBy({ x: xMovement, y: yMovement })
        autoPanId = requestAnimationFrame(autoPan)
      }

      // Stays the same for all consecutive pointermove events
      const fromHandle = {
        ...fromHandleInternal,
        nodeId: unref(nodeId),
        type: handleType,
        position: fromHandleInternal.position,
      }

      const fromNodeInternal = nodeLookup.value.get(unref(nodeId))

      const from = getHandlePosition(
        fromNodeInternal,
        fromHandle,
        Position.Left,
        true
      )

      const newConnection = {
        inProgress: true,
        isValid: null,

        from,
        fromHandle,
        fromPosition: fromHandle.position,
        fromNode: fromNodeInternal,

        to: connectionPosition,
        toHandle: null,
        toPosition: oppositePosition[fromHandle.position],
        toNode: null,
      }

      startConnection(
        {
          nodeId: unref(nodeId),
          id: unref(handleId),
          type: handleType,
          position:
            clickedHandle?.getAttribute('data-handlepos') || Position.Top,
        },
        {
          x: x - containerBounds.left,
          y: y - containerBounds.top,
        }
      )

      emits.connectStart({
        event,
        nodeId: unref(nodeId),
        handleId: unref(handleId),
        handleType,
      })

      let previousConnection = newConnection

      const onPointerMove = function (event) {
        connectionPosition = getEventPosition(event, containerBounds)

        closestHandle = getClosestHandle(
          pointToRendererPoint(
            connectionPosition,
            viewport.value,
            false,
            [1, 1]
          ),
          connectionRadius.value,
          nodeLookup.value,
          fromHandle
        )

        if (!autoPanStarted) {
          autoPan()
          autoPanStarted = true
        }

        const result = isValidHandle(
          event,
          {
            handle: closestHandle,
            connectionMode: connectionMode.value,
            fromNodeId: unref(nodeId),
            fromHandleId: unref(handleId),
            fromType: isTarget ? 'target' : 'source',
            isValidConnection: isValidConnectionHandler,
            doc,
            lib: 'vue',
            flowId,
            nodeLookup: nodeLookup.value,
          },
          edges.value,
          nodes.value,
          findNode
        )

        handleDomNode = result.handleDomNode
        connection = result.connection
        isValid = isConnectionValid(!!closestHandle, result.isValid)

        const newConnection = {
          // from stays the same
          ...previousConnection,
          isValid,
          to:
            closestHandle && isValid
              ? rendererPointToPoint(
                  { x: closestHandle.x, y: closestHandle.y },
                  viewport.value
                )
              : connectionPosition,
          toHandle: result.toHandle,
          toPosition:
            isValid && result.toHandle
              ? result.toHandle.position
              : oppositePosition[fromHandle.position],
          toNode: result.toHandle
            ? nodeLookup.value.get(result.toHandle.nodeId)
            : null,
        }

        // we don't want to trigger an update when the connection
        // is snapped to the same handle as before
        if (
          isValid &&
          closestHandle &&
          previousConnection?.toHandle &&
          newConnection.toHandle &&
          previousConnection.toHandle.type === newConnection.toHandle.type &&
          previousConnection.toHandle.nodeId ===
            newConnection.toHandle.nodeId &&
          previousConnection.toHandle.id === newConnection.toHandle.id &&
          previousConnection.to.x === newConnection.to.x &&
          previousConnection.to.y === newConnection.to.y
        ) {
          return
        }

        updateConnection(
          closestHandle && isValid
            ? rendererPointToPoint(
                {
                  x: closestHandle.x,
                  y: closestHandle.y,
                },
                viewport.value
              )
            : connectionPosition,
          result.toHandle,
          getConnectionStatus(!!closestHandle, isValid)
        )

        previousConnection = newConnection

        if (!closestHandle && !isValid && !handleDomNode) {
          return resetRecentHandle(prevActiveHandle)
        }

        if (
          connection &&
          connection.source !== connection.target &&
          handleDomNode
        ) {
          resetRecentHandle(prevActiveHandle)

          prevActiveHandle = handleDomNode

          // todo: remove `vue-flow__handle-connecting` in next major version
          handleDomNode.classList.add(
            'connecting',
            'vue-flow__handle-connecting'
          )
          handleDomNode.classList.toggle('valid', !!isValid)
          // todo: remove this in next major version
          handleDomNode.classList.toggle('vue-flow__handle-valid', !!isValid)
        }
      }

      const onPointerUp = function (event) {
        if ((closestHandle || handleDomNode) && connection && isValid) {
          if (!onEdgeUpdate) {
            emits.connect(connection)
          } else {
            onEdgeUpdate(event, connection)
          }
        }

        emits.connectEnd(event)

        if (edgeUpdaterType) {
          onEdgeUpdateEnd?.(event)
        }

        resetRecentHandle(prevActiveHandle)

        cancelAnimationFrame(autoPanId)
        endConnection(event)

        autoPanStarted = false
        isValid = false
        connection = null
        handleDomNode = null

        doc.removeEventListener('mousemove', onPointerMove)
        doc.removeEventListener('mouseup', onPointerUp)

        doc.removeEventListener('touchmove', onPointerMove)
        doc.removeEventListener('touchend', onPointerUp)
      }

      doc.addEventListener('mousemove', onPointerMove)
      doc.addEventListener('mouseup', onPointerUp)

      doc.addEventListener('touchmove', onPointerMove)
      doc.addEventListener('touchend', onPointerUp)
    }
  }

  function handleClick(event) {
    if (!connectOnClick.value) {
      return
    }

    const isTarget = unref(type) === 'target'

    if (!connectionClickStartHandle.value) {
      emits.clickConnectStart({
        event,
        nodeId: unref(nodeId),
        handleId: unref(handleId),
      })

      startConnection(
        {
          nodeId: unref(nodeId),
          type: unref(type),
          id: unref(handleId),
          position: Position.Top,
        },
        undefined,
        true
      )

      return
    }

    let isValidConnectionHandler =
      unref(isValidConnection) || isValidConnectionProp.value || alwaysValid

    const node = findNode(unref(nodeId))

    if (!isValidConnectionHandler && node) {
      isValidConnectionHandler =
        (!isTarget ? node.isValidTargetPos : node.isValidSourcePos) ||
        alwaysValid
    }

    if (
      node &&
      (typeof node.connectable === 'undefined'
        ? nodesConnectable.value
        : node.connectable) === false
    ) {
      return
    }

    const doc = getHostForElement(event.target)

    const result = isValidHandle(
      event,
      {
        handle: {
          nodeId: unref(nodeId),
          id: unref(handleId),
          type: unref(type),
          position: Position.Top,
        },
        connectionMode: connectionMode.value,
        fromNodeId: connectionClickStartHandle.value.nodeId,
        fromHandleId: connectionClickStartHandle.value.id || null,
        fromType: connectionClickStartHandle.value.type,
        isValidConnection: isValidConnectionHandler,
        doc,
        lib: 'vue',
        flowId,
        nodeLookup: nodeLookup.value,
      },
      edges.value,
      nodes.value,
      findNode
    )

    const isOwnHandle = result.connection?.source === result.connection?.target

    if (result.isValid && result.connection && !isOwnHandle) {
      emits.connect(result.connection)
    }

    emits.clickConnectEnd(event)

    endConnection(event, true)
  }

  return {
    handlePointerDown,
    handleClick,
  }
}
