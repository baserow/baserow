import { computed, ref, onUnmounted, inject, unref } from 'vue'

/**
 * Manages the drag-source behaviour of a builder element in the page preview.
 *
 * Responsibilities:
 *  - Activate the HTML5 draggable attribute only while the drag handle is held
 *    down
 *  - Write / clear the shared dndContext when a drag starts or ends.
 *  - Clean up the mouseup listener automatically when the component unmounts.
 *
 * @param {Function} getElement
 * @returns {{ isDraggable: Ref<boolean>, onDragHandleMouseDown: Function,
 *   onDragStart: Function, onDragEnd: Function }}
 */
export function useElementDraggable({
  element,
  dragImageHiddenAttribute = null,
  dragImageScale = 0.6,
}) {
  const dndContext = inject('dndContext')

  const isDraggable = ref(false)
  let dragImageContainer = null

  function resetDraggable() {
    isDraggable.value = false
  }

  function removeDragImage() {
    if (dragImageContainer?.parentNode) {
      dragImageContainer.parentNode.removeChild(dragImageContainer)
    }
    dragImageContainer = null
  }

  function createDragImage(source, rect) {
    removeDragImage()

    const clone = source.cloneNode(true)
    const container = document.createElement('div')
    const elements = [clone]

    // Hide all elements that have the dragImageHiddenAttribute.
    while (elements.length > 0) {
      const element = elements.pop()

      if (
        dragImageHiddenAttribute &&
        element.hasAttribute(dragImageHiddenAttribute)
      ) {
        element.style.display = 'none'
      }

      elements.push(...Array.from(element.children))
    }

    Object.assign(container.style, {
      position: 'fixed',
      top: '0',
      left: '0',
      width: `${rect.width * dragImageScale}px`,
      height: `${rect.height * dragImageScale}px`,
      overflow: 'hidden',
      opacity: '0.01',
      pointerEvents: 'none',
      zIndex: '-1',
    })

    Object.assign(clone.style, {
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      transform: `scale(${dragImageScale})`,
      transformOrigin: 'top left',
    })

    container.appendChild(clone)
    document.body.appendChild(container)
    dragImageContainer = container

    return { element: container, scale: dragImageScale }
  }

  const isDragged = computed(() => {
    return dndContext.draggedElement?.id === unref(element).id
  })

  function onDragHandleMouseDown() {
    isDraggable.value = true
    window.addEventListener('mouseup', resetDraggable, { once: true })
  }

  function onDragStart(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    const dragImageInfo = createDragImage(event.currentTarget, rect)
    const pointerOffsetX = (event.clientX - rect.left) * dragImageInfo.scale
    const pointerOffsetY = (event.clientY - rect.top) * dragImageInfo.scale

    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(unref(element).id))
    event.dataTransfer.setDragImage(
      dragImageInfo.element,
      pointerOffsetX,
      pointerOffsetY
    )

    dndContext.draggedElement = unref(element)
  }

  function onDragEnd() {
    removeDragImage()
    dndContext.draggedElement = null
    dndContext.dropTargetId = null
    isDraggable.value = false
  }

  onUnmounted(() => {
    window.removeEventListener('mouseup', resetDraggable)
    removeDragImage()
  })

  return {
    isDraggable,
    isDragged,
    onDragHandleMouseDown,
    onDragStart,
    onDragEnd,
  }
}
