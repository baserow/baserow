import { ref } from 'vue'
import { useVueFlow } from '@vue2-flow/core'
import { nextTick } from '@nuxtjs/composition-api'
import {
  DATA_NODE_WIDTH,
  DATA_NODE_HEIGHT,
  DRAG_THRESHOLD,
} from '@baserow/modules/automation/utils/constants'

export function useWorkflowDragAndDrop(
  nodes,
  positions,
  workflowReadOnly,
  automation,
  app,
  emit
) {
  const { onNodeDragStart, onNodeDrag, onNodeDragStop } = useVueFlow()

  // === DRAG & DROP STATE ===
  const isNodeDragging = ref(false)
  const initialDragPosition = ref(null)
  const draggedNodeId = ref(null)
  const dropZoneActive = ref(null)
  const ghostNode = ref(null)

  // State for delayed drag detection
  const isPotentialDrag = ref(false)
  const potentialDragNodeId = ref(null)
  const initialMousePosition = ref(null)

  /**
   * Checks if a node can be dragged based on its type
   */
  const isNodeDraggable = (nodeData, nodeType) => {
    return nodeData.type !== 'router' && !nodeType.isTrigger
  }

  /**
   * Checks if a drop zone is valid (wouldn't result in same position)
   */
  const isValidDropZone = (draggedNodeId, targetNodeId, targetNodeOutput) => {
    const draggedNode = nodes.value.find((n) => n.id === draggedNodeId)

    if (!draggedNode) {
      return false
    }

    // A drop zone is invalid if the dragged node is already in that position.
    return !(
      draggedNode.previous_node_id === targetNodeId &&
      draggedNode.previous_node_output === targetNodeOutput
    )
  }

  /**
   * Creates a ghost node that will be used for dragging instead of the original node.
   * This provides a better UX by keeping the original node in place and edges stable.
   */
  const createGhostNode = (nodeId, originalNodeData, nodePosition) => {
    const nodeType = app.$registry.get('node', originalNodeData.type)
    if (!nodeType) return null

    return {
      type: 'workflow-node',
      id: `ghost-${nodeId}`,
      label: nodeType.getLabel({
        automation: automation.value,
        node: originalNodeData,
      }),
      position: { x: nodePosition.x, y: nodePosition.y },
      draggable: true,
      data: {
        nodeId: originalNodeData.id,
        isTrigger: nodeType.isTrigger,
        readOnly: workflowReadOnly.value,
        debug: workflowReadOnly.value, // Keep debug styling consistent
        outputUid: originalNodeData.previous_node_output || '',
        isGhost: true,
        node: originalNodeData,
      },
    }
  }

  /**
   * Programmatically starts dragging the ghost node by dispatching a synthetic mousedown event.
   * This creates the seamless drag experience where clicking the original node immediately
   * starts dragging the ghost.
   */
  const startGhostDrag = (nodeId) => {
    const ghostElement = document.querySelector(`[data-id="ghost-${nodeId}"]`)
    if (!ghostElement) return

    const rect = ghostElement.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2

    const syntheticMouseDown = new MouseEvent('mousedown', {
      view: window,
      bubbles: true,
      cancelable: true,
      clientX: centerX,
      clientY: centerY,
      button: 0,
      buttons: 1,
    })

    ghostElement.dispatchEvent(syntheticMouseDown)
  }

  const startDrag = (nodeId) => {
    if (!nodeId) return

    const originalNodeData = nodes.value.find((n) => n.id === nodeId)
    const nodePosition = positions.value[nodeId]

    if (!originalNodeData || !nodePosition) return

    ghostNode.value = createGhostNode(nodeId, originalNodeData, nodePosition)
    if (!ghostNode.value) {
      cleanupPotentialDrag()
      return
    }

    isNodeDragging.value = true
    draggedNodeId.value = nodeId
    initialDragPosition.value = { ...nodePosition }

    nextTick(() => {
      startGhostDrag(nodeId)
    })
  }

  const handleMouseMove = (event) => {
    if (!isPotentialDrag.value) return

    const dx = event.clientX - initialMousePosition.value.x
    const dy = event.clientY - initialMousePosition.value.y
    const distance = Math.sqrt(dx * dx + dy * dy)

    if (distance > DRAG_THRESHOLD) {
      const nodeIdToDrag = potentialDragNodeId.value
      cleanupPotentialDrag()
      startDrag(nodeIdToDrag)
    }
  }

  const handleMouseUp = () => {
    if (isPotentialDrag.value) {
      // It was a click, not a drag. Select the node.
      emit('input', potentialDragNodeId.value)
    }
    cleanupPotentialDrag()
  }

  const cleanupPotentialDrag = () => {
    isPotentialDrag.value = false
    potentialDragNodeId.value = null
    initialMousePosition.value = null
    window.removeEventListener('mousemove', handleMouseMove)
    window.removeEventListener('mouseup', handleMouseUp, { once: true })
  }

  const handlePrepareGhost = (nodeIdStr, event) => {
    const nodeId = parseInt(nodeIdStr)

    if (isNodeDragging.value || isPotentialDrag.value) return

    const originalNodeData = nodes.value.find((n) => n.id === nodeId)
    if (!originalNodeData) return

    const nodeType = app.$registry.get('node', originalNodeData.type)
    if (!isNodeDraggable(originalNodeData, nodeType)) {
      return
    }

    isPotentialDrag.value = true
    potentialDragNodeId.value = nodeId
    initialMousePosition.value = { x: event.clientX, y: event.clientY }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp, { once: true })
  }

  const checkDropZoneHover = (dragPosition) => {
    if (!isNodeDragging.value || !draggedNodeId.value) return

    let activeZone = null

    // Get all add button positions from all nodes except the dragged one
    Object.values(positions.value).forEach((nodePos) => {
      if (nodePos.addButtonPositions) {
        nodePos.addButtonPositions.forEach((buttonPos) => {
          // Calculate if the dragged node overlaps with this button position
          const buttonRect = {
            x: buttonPos.x - 20, // Add some padding around the button
            y: buttonPos.y - 20,
            width: 40,
            height: 40,
          }

          const dragRect = {
            x: dragPosition.x,
            y: dragPosition.y,
            width: DATA_NODE_WIDTH,
            height: DATA_NODE_HEIGHT,
          }

          // Check for overlap
          if (
            dragRect.x < buttonRect.x + buttonRect.width &&
            dragRect.x + dragRect.width > buttonRect.x &&
            dragRect.y < buttonRect.y + buttonRect.height &&
            dragRect.y + dragRect.height > buttonRect.y
          ) {
            // Before setting as active zone, check if this button is actually a valid drop zone
            const parts = buttonPos.key.split('-')
            if (parts.length >= 2) {
              const buttonNodeId = parseInt(parts[1])

              // Apply the same logic as in displayNodes to determine if it's a valid drop zone
              let isValidDropZoneResult = false
              if (draggedNodeId.value !== buttonNodeId) {
                isValidDropZoneResult = isValidDropZone(
                  draggedNodeId.value,
                  buttonNodeId,
                  buttonPos.uid
                )
              }

              // Only set as active zone if it's a valid drop zone
              if (isValidDropZoneResult) {
                activeZone = {
                  key: buttonPos.key,
                  uid: buttonPos.uid,
                  nodeId: buttonNodeId,
                }
              }
            }
          }
        })
      }
    })

    dropZoneActive.value = activeZone
  }

  const cleanupGhostState = () => {
    isNodeDragging.value = false
    draggedNodeId.value = null
    ghostNode.value = null
    dropZoneActive.value = null
  }

  onNodeDragStart(({ node }) => {
    // Allow ghost nodes to be dragged
    if (node.id.startsWith('ghost-')) {
      const originalNodeId = parseInt(node.id.replace('ghost-', ''))
      const originalNodeData = nodes.value.find((n) => n.id === originalNodeId)
      if (
        originalNodeData &&
        !isNodeDraggable(
          originalNodeData,
          app.$registry.get('node', originalNodeData.type)
        )
      ) {
        cleanupGhostState()
        return false // Don't allow dragging non-draggable nodes' ghosts
      }
      return true
    }

    // Block original nodes when ghost system is active
    if (node.type === 'workflow-node') {
      if (isNodeDragging.value && ghostNode.value) {
        return false // Ghost is handling the drag
      }
    }

    return false // Only ghost nodes should be draggable
  })

  onNodeDrag(({ node }) => {
    // Update ghost node position and check drop zones
    if (node.id.startsWith('ghost-') && isNodeDragging.value) {
      if (ghostNode.value) {
        ghostNode.value.position = { ...node.position }
      }
      checkDropZoneHover(node.position)
    }
  })

  onNodeDragStop(({ node }) => {
    // Only handle ghost node drag stops
    if (!node.id.startsWith('ghost-')) return

    const wasDroppedOnZone = dropZoneActive.value !== null
    const droppedZone = dropZoneActive.value
    const originalNodeId = draggedNodeId.value

    cleanupGhostState()

    if (!workflowReadOnly.value && originalNodeId) {
      if (wasDroppedOnZone && droppedZone) {
        emit('reorder-nodes', {
          draggedNodeId: originalNodeId,
          targetNodeId: droppedZone.nodeId,
          targetNodeOutput: droppedZone.uid,
        })
      }
    }
  })

  return {
    isNodeDragging,
    draggedNodeId,
    dropZoneActive,
    ghostNode,
    handlePrepareGhost,
    isNodeDraggable,
    isValidDropZone,
    checkDropZoneHover,
  }
}
