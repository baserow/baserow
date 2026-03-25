<template>
  <div
    class="column-element"
    :style="{
      '--space-between-columns': `${element.column_gap}px`,
      '--alignment': flexAlignment,
    }"
  >
    <div
      v-for="(childrenInColumn, columnIndex) in childrenElements"
      :key="columnIndex"
      class="column-element__column"
      :class="{
        'column-element__column--drop-active':
          isDragging && dragOverColumnIndex === columnIndex,
      }"
      :style="{ '--column-width': `${columnWidth}%` }"
    >
      <template v-if="childrenInColumn.length > 0">
        <div
          v-for="childCurrent in childrenInColumn"
          :key="childCurrent.id"
          class="column-element__element"
        >
          <ElementPreview
            v-if="mode === 'editing'"
            :element="childCurrent"
            :application-context-additions="applicationContextAdditions"
            @move="$emit('move', $event)"
          ></ElementPreview>
          <PageElement
            v-else
            :element="childCurrent"
            :mode="mode"
            :application-context-additions="applicationContextAdditions"
          ></PageElement>
        </div>
      </template>
      <AddElementZone
        v-else-if="
          mode === 'editing' &&
          !isDragging &&
          $hasPermission(
            'builder.page.create_element',
            elementPage,
            workspace.id
          )
        "
        :page="elementPage"
        @add-element="showAddElementModal(columnIndex)"
      />
      <!-- Drop zone: only for empty columns during drag.
           Non-empty columns rely on ElementPreview's before/after indicators. -->
      <div
        v-if="mode === 'editing' && isDragging && childrenInColumn.length === 0"
        class="column-element__drop-zone"
        @dragover.prevent.stop="onColumnDragOver(columnIndex)"
        @dragleave="onColumnDragLeave(columnIndex, $event)"
        @drop.prevent.stop="onDropInColumn(columnIndex)"
      />
    </div>
    <AddElementModal ref="addElementModal" :page="elementPage" />
  </div>
</template>

<script>
import _ from 'lodash'

import { notifyIf } from '@baserow/modules/core/utils/error'
import AddElementZone from '@baserow/modules/builder/components/elements/AddElementZone'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal'
import containerElement from '@baserow/modules/builder/mixins/containerElement'
import PageElement from '@baserow/modules/builder/components/page/PageElement'
import ElementPreview from '@baserow/modules/builder/components/elements/ElementPreview'
import { VERTICAL_ALIGNMENTS } from '@baserow/modules/builder/enums'
import { dimensionMixin } from '@baserow/modules/core/mixins/dimensions'

export default {
  name: 'ColumnElement',
  components: {
    AddElementZone,
    ElementPreview,
    PageElement,
    AddElementModal,
  },
  mixins: [containerElement, dimensionMixin],
  inject: ['dndContext'],
  props: {
    /**
     * @type {Object}
     * @property {number} column_amount - The amount of columns
     * @property {number} column_gap - The space between the columns
     * @property {string} alignment - The alignment of the columns
     */
    element: {
      type: Object,
      required: true,
    },
    applicationContextAdditions: {
      type: Object,
      required: false,
      default: null,
    },
  },
  emits: ['move'],
  data() {
    return {
      dragOverColumnIndex: null,
    }
  },
  computed: {
    isDragging() {
      const dragged = this.dndContext?.draggedElement
      if (!dragged || dragged.page_id !== this.element.page_id) return false
      const draggedElementType = this.$registry.get('element', dragged.type)
      return (
        draggedElementType.isDisallowedReason({
          workspace: this.workspace,
          builder: this.builder,
          page: this.elementPage,
          parentElement: this.element,
          beforeElement: null,
          placeInContainer: '0',
          pagePlace: this.elementType.getPagePlace(),
        }) === null
      )
    },
    flexAlignment() {
      const alignmentMapping = {
        [VERTICAL_ALIGNMENTS.TOP]: 'flex-start',
        [VERTICAL_ALIGNMENTS.CENTER]: 'center',
        [VERTICAL_ALIGNMENTS.BOTTOM]: 'flex-end',
      }
      return alignmentMapping[this.element.alignment]
    },
    breakingPoint() {
      const minColumnWidth = 130
      const totalColumnWidth = minColumnWidth * this.element.column_amount
      const totalColumnGap =
        this.element.column_gap * (this.element.column_amount - 1)
      const extraPadding = 120

      return totalColumnWidth + totalColumnGap + extraPadding
    },
    columnAmount() {
      if (
        this.dimensions.width !== null &&
        this.dimensions.width < this.breakingPoint
      ) {
        return 1
      } else {
        return this.element.column_amount
      }
    },
    columnWidth() {
      return 100 / this.columnAmount - 0.00000000000001
    },
    childrenByColumnOrdered() {
      return _.groupBy(this.children, (child) => {
        const childCol = parseInt(child.place_in_container, 10)
        return childCol > this.columnAmount - 1
          ? this.columnAmount - 1
          : childCol
      })
    },
    childrenElements() {
      return [...Array(this.columnAmount).keys()].map(
        (columnIndex) => this.childrenByColumnOrdered[columnIndex] || []
      )
    },
  },
  mounted() {
    this.dimensions.targetElement = this.$el.parentElement
  },
  methods: {
    showAddElementModal(columnIndex) {
      this.$refs.addElementModal.show({
        placeInContainer: `${columnIndex}`,
        parentElementId: this.element.id,
      })
    },
    onColumnDragOver(columnIndex) {
      this.dragOverColumnIndex = columnIndex
    },
    onColumnDragLeave(columnIndex, event) {
      this.dragOverColumnIndex = null
    },
    async onDropInColumn(columnIndex) {
      const dragged = this.dndContext?.draggedElement
      if (!dragged) return

      if (dragged.page_id !== this.element.page_id) {
        this.dragOverColumnIndex = null
        return
      }

      // Validate the element type is allowed inside this column
      const draggedElementType = this.$registry.get('element', dragged.type)
      const reason = draggedElementType.isDisallowedReason({
        workspace: this.workspace,
        builder: this.builder,
        page: this.elementPage,
        parentElement: this.element,
        beforeElement: null,
        placeInContainer: `${columnIndex}`,
        pagePlace: this.elementType.getPagePlace(),
      })
      if (reason) {
        this.dragOverColumnIndex = null
        return
      }

      this.dragOverColumnIndex = null
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

      try {
        await this.$store.dispatch('element/move', {
          builder: this.builder,
          page: draggedPage,
          elementId: dragged.id,
          beforeElementId: null,
          parentElementId: this.element.id,
          placeInContainer: `${columnIndex}`,
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
