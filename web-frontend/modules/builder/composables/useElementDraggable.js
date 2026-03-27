import { ref, onUnmounted, inject } from 'vue'

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
export function useElementDraggable(getElement) {
  const dndContext = inject('dndContext')

  const isDraggable = ref(false)

  function resetDraggable() {
    isDraggable.value = false
  }

  function onDragHandleMouseDown() {
    isDraggable.value = true
    window.addEventListener('mouseup', resetDraggable, { once: true })
  }

  function onDragStart(event) {
    if (!dndContext) return
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(getElement().id))
    dndContext.draggedElement = getElement()
  }

  function onDragEnd() {
    if (!dndContext) return
    dndContext.draggedElement = null
    dndContext.dropTargetId = null
    dndContext.dropPosition = null
    isDraggable.value = false
  }

  onUnmounted(() => {
    window.removeEventListener('mouseup', resetDraggable)
  })

  return {
    isDraggable,
    onDragHandleMouseDown,
    onDragStart,
    onDragEnd,
  }
}
