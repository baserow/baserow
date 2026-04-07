import { computed, inject, ref, unref } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import { notifyIf } from '@baserow/modules/core/utils/error'

export function useDropElementTarget({
  parentElement,
  referenceElement = null,
  placeInContainer = null,
  page = null,
}) {
  const store = useStore()
  const uid = useId()

  const { $registry, $hasPermission } = useNuxtApp()

  const workspace = inject('workspace')
  const builder = inject('builder')

  const dndContext = inject('dndContext')

  const dropPosition = ref(null)

  const draggedElement = computed(() => dndContext?.draggedElement ?? null)
  const isDragOver = computed(() => dndContext?.dropTargetId === uid)

  const targetPage = computed(() => {
    if (unref(referenceElement)) {
      return store.getters['page/getById'](
        builder,
        unref(referenceElement).page_id
      )
    }
    if (unref(parentElement)) {
      return store.getters['page/getById'](
        builder,
        unref(parentElement).page_id
      )
    }
    return unref(page)
  })

  const resolvedParentElement = computed(() => {
    const reference = unref(referenceElement)

    if (reference) {
      return store.getters['element/getParent'](targetPage.value, reference)
    }

    return unref(parentElement)
  })

  const resolvedBeforeElement = computed(() => {
    const reference = unref(referenceElement)

    if (!reference) {
      return null
    }

    if (dropPosition.value === 'after') {
      return store.getters['element/getNextElement'](
        targetPage.value,
        reference
      )
    }

    return reference
  })

  const resolvedPagePlace = computed(() => {
    if (!draggedElement.value) {
      return null
    }
    return draggedElementType.value.getPagePlace()
  })

  const referencePagePlace = computed(() => {
    const reference = unref(referenceElement)
    if (!reference || !$registry.exists('element', reference.type)) {
      return null
    }
    return $registry.get('element', reference.type).getPagePlace()
  })

  const draggedElementType = computed(() => {
    const dragged = draggedElement.value
    if (!dragged) {
      return null
    }

    return $registry.get('element', dragged.type)
  })

  const isValidDropTarget = computed(() => {
    const draggedType = draggedElementType.value
    if (!draggedType) {
      return false
    }

    const draggedElt = draggedElement.value

    // If the reference element is the dragged element it's not a valid target
    if (
      draggedElt.id === unref(referenceElement)?.id ||
      draggedElt.id === unref(parentElement)?.id
    ) {
      return false
    }

    return (
      draggedType.isDisallowedReason({
        workspace,
        builder,
        page: targetPage.value,
        element: draggedElt,
        parentElement: resolvedParentElement.value,
        beforeElement: resolvedBeforeElement.value,
        placeInContainer: unref(placeInContainer),
        pagePlace: resolvedPagePlace.value,
        referencePagePlace: referencePagePlace.value,
      }) === null
    )
  })

  const isDropTarget = computed(() => isDragOver.value)

  let dragEnterCount = 0

  function clearState() {
    dndContext.dropTargetId = null
    dropPosition.value = null
    dragEnterCount = 0
  }

  function syncDropPosition(event) {
    if (!unref(referenceElement)) {
      return null
    }

    const rect = event.currentTarget.getBoundingClientRect()
    const position =
      event.clientY < rect.top + rect.height / 2 ? 'before' : 'after'

    dropPosition.value = position

    return position
  }

  function onDragEnterHandler(event) {
    if (!draggedElement.value) {
      return
    }

    if (!isValidDropTarget.value) {
      // When the cursor re-enters the dragged element's own preview, stop
      // propagation so the parent container doesn't claim the drop zone.
      // Without this, a tiny drag within the element immediately makes its
      // parent the active drop target.
      const isOverDragSource =
        draggedElement.value.id === unref(referenceElement)?.id ||
        draggedElement.value.id === unref(parentElement)?.id
      if (isOverDragSource) {
        event.stopPropagation()
      }
      return
    }

    dragEnterCount++
    dndContext.dropTargetId = uid

    // Prevent the parent drop target from counting this enter
    event.stopPropagation()
  }

  function onDragOverHandler(event) {
    const dragged = draggedElement.value
    if (!dragged) {
      return
    }

    if (!isValidDropTarget.value) {
      if (dragEnterCount > 0) {
        clearState()
      }
      return
    }

    syncDropPosition(event)

    event.preventDefault()
    event.stopPropagation()
  }

  function onDragLeaveHandler(event) {
    if (dragEnterCount === 0) {
      return
    }

    dragEnterCount--

    if (dragEnterCount === 0) {
      clearState()
    }

    event.stopPropagation()
  }

  async function onDropHandler(event) {
    const dragged = draggedElement.value
    if (!dragged) {
      return
    }

    // Only process the drop if this zone was the active drop target (indicator
    // was visible). Without this guard, a quick drag-and-release would bubble up
    // to a parent drop zone and trigger an unintended move.
    if (!isDragOver.value) {
      return
    }

    syncDropPosition(event)

    if (!isValidDropTarget.value) {
      clearState()
      return
    }

    event.preventDefault()
    event.stopPropagation()

    if (!$hasPermission('builder.page.element.update', dragged, workspace.id)) {
      clearState()
      return
    }

    const reason = draggedElementType.value.isDisallowedReason({
      workspace,
      builder,
      page: targetPage.value,
      element: dragged,
      parentElement: resolvedParentElement.value,
      beforeElement: resolvedBeforeElement.value,
      placeInContainer: unref(placeInContainer),
      pagePlace: resolvedPagePlace.value,
      referencePagePlace: referencePagePlace.value,
    })

    if (reason) {
      clearState()
      return
    }

    const draggedPage = store.getters['page/getById'](builder, dragged.page_id)

    try {
      await store.dispatch('element/move', {
        builder,
        page: draggedPage,
        elementId: dragged.id,
        beforeElementId: resolvedBeforeElement.value?.id || null,
        parentElementId: resolvedParentElement.value?.id || null,
        placeInContainer: unref(placeInContainer),
        targetPage: targetPage.value,
      })
    } catch (error) {
      notifyIf(error)
    } finally {
      clearState()
    }
  }

  return {
    draggedElement,
    draggedElementType,
    dropPosition,
    isDragOver,
    isDropTarget,
    isValidDropTarget,
    onDragEnter: onDragEnterHandler,
    onDragOver: onDragOverHandler,
    onDragLeave: onDragLeaveHandler,
    onDrop: onDropHandler,
  }
}
