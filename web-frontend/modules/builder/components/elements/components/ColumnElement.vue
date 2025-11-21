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
      :style="getColumnStyle(columnIndex)"
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
          $hasPermission(
            'builder.page.create_element',
            elementPage,
            workspace.id
          )
        "
        :page="elementPage"
        @add-element="showAddElementModal(columnIndex)"
      />
    </div>
    <AddElementModal ref="addElementModal" :page="elementPage" />
  </div>
</template>

<script>
import _ from 'lodash'

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
  computed: {
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
    columnWidths() {
      const { layout_type: layoutType, column_widths: customWidths } = this.element

      switch (layoutType) {
        case 'auto':
          return Array(this.columnAmount).fill(100 / this.columnAmount)
        case '1:2':
          return this.columnAmount === 2 ? [33.33, 66.67] : this.getAutoWidths()
        case '2:1':
          return this.columnAmount === 2 ? [66.67, 33.33] : this.getAutoWidths()
        case '1:1:2':
          return this.columnAmount === 3 ? [25, 25, 50] : this.getAutoWidths()
        case '2:1:1':
          return this.columnAmount === 3 ? [50, 25, 25] : this.getAutoWidths()
        case 'custom':
          return this.calculateCustomWidths(customWidths)
        default:
          return this.getAutoWidths()
      }
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
    getAutoWidths() {
      return Array(this.columnAmount).fill(100 / this.columnAmount)
    },
    calculateCustomWidths(customWidths) {
      if (!customWidths || customWidths.length !== this.columnAmount) {
        return this.getAutoWidths()
      }

      const fixedTotal = customWidths.reduce((sum, width) => {
        if (typeof width === 'number') {
          return sum + width
        }
        return sum
      }, 0)

      const dynamicCount = customWidths.filter(
        (w) => w === 'dynamic' || w === 'auto'
      ).length

      if (dynamicCount === 0) {
        const total = customWidths.reduce((sum, w) => sum + (w || 0), 0)
        return customWidths.map((w) => ((w || 0) / total) * 100)
      }

      const containerWidth = this.dimensions.width || 1000
      const gapTotal = this.element.column_gap * (this.columnAmount - 1)
      const availableWidth = containerWidth - gapTotal - fixedTotal
      const dynamicWidth = Math.max(0, availableWidth / dynamicCount)

      const totalPx = fixedTotal + dynamicWidth * dynamicCount
      return customWidths.map((w) => {
        const px = typeof w === 'number' ? w : dynamicWidth
        return (px / totalPx) * 100
      })
    },
    getColumnStyle(columnIndex) {
      const width = this.columnWidths[columnIndex]
      return {
        '--column-width': `${width}%`,
      }
    },
  },
}
</script>
