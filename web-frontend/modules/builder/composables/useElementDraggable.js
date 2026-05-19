import { computed, ref, onUnmounted, inject, unref } from 'vue'

const DRAG_IMAGE_SCALE = 0.6

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
export function useElementDraggable({ element }) {
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

    clone
      .querySelectorAll(
        '.element-preview__insert, .element-preview__menu, .element-preview__tags'
      )
      .forEach((element) => {
        element.style.display = 'none'
      })

    Object.assign(container.style, {
      position: 'fixed',
      top: '0',
      left: '0',
      width: `${rect.width * DRAG_IMAGE_SCALE}px`,
      height: `${rect.height * DRAG_IMAGE_SCALE}px`,
      overflow: 'hidden',
      opacity: '0.01',
      pointerEvents: 'none',
      zIndex: '-1',
    })

    Object.assign(clone.style, {
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      transform: `scale(${DRAG_IMAGE_SCALE})`,
      transformOrigin: 'top left',
    })

    container.appendChild(clone)
    document.body.appendChild(container)
    dragImageContainer = container

    return { element: container, scale: DRAG_IMAGE_SCALE }
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
