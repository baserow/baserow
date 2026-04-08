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
export function useElementDraggable({ element }) {
  const dndContext = inject('dndContext')

  const isDraggable = ref(false)

  function resetDraggable() {
    isDraggable.value = false
  }

  const isDragged = computed(() => {
    return dndContext.draggedElement?.id === unref(element).id
  })

  function onDragHandleMouseDown() {
    isDraggable.value = true
    window.addEventListener('mouseup', resetDraggable, { once: true })
  }

  function onDragStart(event) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(unref(element).id))
    dndContext.draggedElement = unref(element)
  }

  function onDragEnd() {
    dndContext.draggedElement = null
    dndContext.dropTargetId = null
    isDraggable.value = false
  }

  onUnmounted(() => {
    window.removeEventListener('mouseup', resetDraggable)
  })

  return {
    isDraggable,
    isDragged,
    onDragHandleMouseDown,
    onDragStart,
    onDragEnd,
  }
}
