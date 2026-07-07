<template>
  <div
    class="column-element"
    :class="stackingClasses"
    :style="{
      '--space-between-columns': `${element.column_gap}px`,
      '--alignment': flexAlignment,
      '--grid-template-columns': gridTemplateColumns,
    }"
  >
    <div
      v-for="(childrenInColumn, columnIndex) in childrenElements"
      :key="columnIndex"
      class="column-element__column"
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
        v-else-if="mode === 'editing'"
        :disabled="
          !$hasPermission(
            'builder.page.create_element',
            elementPage,
            workspace.id
          )
        "
        :place-in-container="`${columnIndex}`"
        :parent-element="element"
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
import {
  COLUMN_STACKING,
  VERTICAL_ALIGNMENTS,
} from '@baserow/modules/builder/enums'
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
     * @property {string} layout_type - The selected column layout preset
     * @property {Array} column_weights - The custom column weights
     * @property {Object} column_stacking - The stacking behavior per device type
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
  computed: {
    flexAlignment() {
      const alignmentMapping = {
        [VERTICAL_ALIGNMENTS.TOP]: 'flex-start',
        [VERTICAL_ALIGNMENTS.CENTER]: 'center',
        [VERTICAL_ALIGNMENTS.BOTTOM]: 'flex-end',
      }
      return alignmentMapping[this.element.alignment]
    },

    shouldStackColumns() {
      const currentDeviceType =
        this.$store.getters['page/getDeviceTypeSelected']
      return (
        this.element.column_stacking?.[currentDeviceType] ===
        COLUMN_STACKING.STACKED
      )
    },

    // Enables the public/preview CSS fallback for stacked responsive layouts.
    stackingClasses() {
      return {
        'column-element--public': this.mode !== 'editing',
        'column-element--stack-desktop':
          this.element.column_stacking?.desktop === COLUMN_STACKING.STACKED,
        'column-element--stack-smartphone':
          this.element.column_stacking?.smartphone === COLUMN_STACKING.STACKED,
        'column-element--stack-tablet':
          this.element.column_stacking?.tablet === COLUMN_STACKING.STACKED,
      }
    },

    gridTemplateColumns() {
      if (this.element.column_amount === 1) {
        return '1fr'
      }

      if (this.shouldStackColumns) {
        return '1fr'
      }

      const layoutType = this.element.layout_type
      if (
        layoutType === 'custom' &&
        this.element.column_weights &&
        this.element.column_weights.length === this.element.column_amount
      ) {
        return this.element.column_weights
          .map((weight) => this.customWeightToGridTrack(weight))
          .join(' ')
      }

      const predefinedLayouts = {
        '1:2': ['1fr', '2fr'],
        '2:1': ['2fr', '1fr'],
        '1:3': ['1fr', '3fr'],
        '3:1': ['3fr', '1fr'],
        '1:1:2': ['1fr', '1fr', '2fr'],
        '2:1:1': ['2fr', '1fr', '1fr'],
        '1:2:1': ['1fr', '2fr', '1fr'],
      }

      if (
        predefinedLayouts[layoutType] &&
        predefinedLayouts[layoutType].length === this.element.column_amount
      ) {
        return predefinedLayouts[layoutType].join(' ')
      }

      return `repeat(${this.element.column_amount}, minmax(0, 1fr))`
    },

    childrenByColumnOrdered() {
      return _.groupBy(this.children, (child) => {
        const childCol = parseInt(child.place_in_container, 10)
        return childCol > this.element.column_amount - 1
          ? this.element.column_amount - 1
          : childCol
      })
    },
    childrenElements() {
      return [...Array(this.element.column_amount).keys()].map(
        (columnIndex) => this.childrenByColumnOrdered[columnIndex] || []
      )
    },
  },

  mounted() {
    this.dimensions.targetElement = this.$el.parentElement
  },
  methods: {
    customWeightToGridTrack(weight) {
      const parsedWeight =
        typeof weight === 'number' ? weight : parseFloat(weight)

      if (Number.isNaN(parsedWeight) || parsedWeight < 0) {
        return '1fr'
      }

      return parsedWeight === 0 ? 'auto' : `${parsedWeight}fr`
    },
    showAddElementModal(columnIndex) {
      this.$refs.addElementModal.show({
        placeInContainer: `${columnIndex}`,
        parentElementId: this.element.id,
      })
    },
  },
}
</script>
