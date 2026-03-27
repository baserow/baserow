import element from '@baserow/modules/builder/mixins/element'
import { DIRECTIONS } from '@baserow/modules/builder/enums'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  mixins: [element],
  inject: ['dndContext'],
  computed: {
    DIRECTIONS: () => DIRECTIONS,
    children() {
      return this.$store.getters['element/getChildren'](
        this.elementPage,
        this.element
      )
    },
    isContainerDragging() {
      const dragged = this.dndContext?.draggedElement
      if (!dragged) return false
      const draggedElementType = this.$registry.get('element', dragged.type)
      return (
        draggedElementType.isDisallowedReason({
          workspace: this.workspace,
          builder: this.builder,
          page: this.elementPage,
          parentElement: this.element,
          beforeElement: null,
          placeInContainer: null,
          pagePlace: this.elementType.getPagePlace(),
        }) === null
      )
    },
  },
  methods: {
    async onContainerDrop() {
      if (!this.isContainerDragging) return

      const dragged = this.dndContext.draggedElement

      this.dndContext.draggedElement = null
      this.dndContext.dropTargetId = null
      this.dndContext.dropPosition = null

      if (
        !this.$hasPermission(
          'builder.page.element.update',
          dragged,
          this.workspace.id
        )
      ) {
        return
      }

      const draggedPage = this.$store.getters['page/getById'](
        this.builder,
        dragged.page_id
      )
      const isCrossPage = dragged.page_id !== this.elementPage.id

      try {
        await this.$store.dispatch('element/move', {
          builder: this.builder,
          page: draggedPage,
          elementId: dragged.id,
          beforeElementId: null,
          parentElementId: this.element.id,
          placeInContainer: null,
          ...(isCrossPage && { targetPage: this.elementPage }),
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
