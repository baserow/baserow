<template>
  <div
    v-scroll="scroll"
    class="simple-grid"
    :class="{
      'simple-grid--full-height': fullHeight,
      'simple-grid--with-footer': withFooter,
      'simple-grid--border': border,
    }"
  >
    <div
      v-if="fixedFields.length > 0 || showRowId"
      ref="left"
      class="simple-grid__left"
    >
      <div class="simple-grid__head">
        <div
          v-if="showRowId"
          class="simple-grid__field simple-grid__field--first"
        ></div>
        <div
          v-for="field in orderedFixedFields"
          :key="field.id"
          class="simple-grid__field"
          :style="{ width: Math.max(getFieldWidth(field), 150) + 'px' }"
        >
          <div class="simple-grid__field-description">
            <i
              class="simple-grid__field-icon"
              :class="fieldTypes[field.type].iconClass"
            ></i>
            {{ field.name }}
          </div>
          <HorizontalResize
            class="simple-grid__field-width"
            :width="getFieldWidth(field)"
            :min="GRID_VIEW_MIN_FIELD_WIDTH"
            @move="moveFieldWidth(field, $event)"
            @update="updateFieldWidth(field, $event)"
          ></HorizontalResize>
        </div>
      </div>
      <div class="simple-grid__body">
        <div
          v-for="row in rows"
          :key="row.id"
          class="simple-grid__row"
          :class="{
            'simple-grid__row--hover':
              showHoveredRow && currentHoveredRow === row.id,
            'simple-grid__row--disabled':
              !multiple && selectedRows.includes(row.id),
            'simple-grid__row--checked':
              multiple && selectedRows.includes(row.id),
          }"
          @click="$emit('row-click', row)"
          @mouseover="currentHoveredRow = row.id"
          @mouseleave="currentHoveredRow = null"
        >
          <div
            v-if="showRowId"
            class="simple-grid__cell simple-grid__cell--first"
          >
            {{ row.id }}
            <div
              v-if="multiple"
              v-show="
                currentHoveredRow === row.id || selectedRows.includes(row.id)
              "
              class="simple-grid__cell-checkbox"
            >
              <Checkbox :checked="selectedRows.includes(row.id)"></Checkbox>
            </div>
          </div>
          <div
            v-for="field in orderedFixedFields"
            :key="field.id"
            class="simple-grid__cell"
            :style="{ width: Math.max(getFieldWidth(field), 150) + 'px' }"
          >
            <SimpleGridField :field="field" :row="row" />
          </div>
        </div>
        <div
          v-if="canAddRow"
          class="simple-grid__row"
          :class="{
            'simple-grid__row--hover': showHoveredRow && addRowHover,
          }"
          @mouseover="addRowHover = true"
          @mouseleave="addRowHover = false"
          @click="$emit('add-row')"
        >
          <a
            class="simple-grid__cell simple-grid__cell--single simple-grid__add-row"
          >
            <i class="iconoir-plus" />
          </a>
        </div>
        <div v-if="withFooter" class="simple-grid__foot">
          <slot name="footLeft"></slot>
        </div>
      </div>
    </div>
    <div class="simple-grid__right-scrollbar-wrapper">
      <Scrollbars
        ref="scrollbars"
        horizontal="getHorizontalScrollbarElement"
        @horizontal="horizontalScroll"
      ></Scrollbars>
      <div ref="right" class="simple-grid__right-wrapper">
        <div class="simple-grid__right">
          <div class="simple-grid__head">
            <div
              v-for="field in visibleOrderedFields"
              :key="field.id"
              class="simple-grid__field"
              :style="{ width: getFieldWidth(field) + 'px' }"
            >
              <div class="simple-grid__field-description">
                <i
                  class="simple-grid__field-icon"
                  :class="fieldTypes[field.type].iconClass"
                ></i>
                {{ field.name }}
              </div>
              <HorizontalResize
                class="simple-grid__field-width"
                :width="getFieldWidth(field)"
                :min="GRID_VIEW_MIN_FIELD_WIDTH"
                @move="moveFieldWidth(field, $event)"
                @update="updateFieldWidth(field, $event)"
              ></HorizontalResize>
            </div>
          </div>
          <div class="simple-grid__body">
            <div
              v-for="row in rows"
              :key="row.id"
              class="simple-grid__row"
              :class="{
                'simple-grid__row--hover':
                  showHoveredRow && currentHoveredRow === row.id,
                'simple-grid__row--disabled':
                  !multiple && selectedRows.includes(row.id),
                'simple-grid__row--checked':
                  multiple && selectedRows.includes(row.id),
              }"
              @click="$emit('row-click', row)"
              @mouseover="currentHoveredRow = row.id"
              @mouseleave="currentHoveredRow = null"
            >
              <div
                v-for="field in visibleOrderedFields"
                :key="field.id"
                class="simple-grid__cell"
                :style="{ width: getFieldWidth(field) + 'px' }"
              >
                <SimpleGridField :field="field" :row="row" />
              </div>
            </div>
            <div
              v-if="canAddRow && visibleOrderedFields.length > 0"
              class="simple-grid__row"
              :class="{
                'simple-grid__row--hover': showHoveredRow && addRowHover,
              }"
              @mouseover="addRowHover = true"
              @mouseleave="addRowHover = false"
              @click="$emit('add-row')"
            >
              <div class="simple-grid__cell simple-grid__cell--single"></div>
            </div>
            <div v-if="withFooter" class="simple-grid__foot"></div>
          </div>
        </div>
      </div>
      <div v-if="withFooter" class="simple-grid__right-wrapper-footer"></div>
    </div>
  </div>
</template>

<script>
import _ from 'lodash'
import {
  filterVisibleFieldsFunction,
  sortFieldsByOrderAndIdFunction,
} from '@baserow/modules/database/utils/view'
import HorizontalResize from '@baserow/modules/core/components/HorizontalResize'
import SimpleGridField from '@baserow/modules/database/components/view/grid/SimpleGridField'
import { GRID_VIEW_MIN_FIELD_WIDTH } from '@baserow/modules/database/constants'

export default {
  name: 'SimpleGrid',
  components: { HorizontalResize, SimpleGridField },
  props: {
    rows: {
      type: Array,
      required: true,
    },
    fixedFields: {
      type: Array,
      required: false,
      default: () => [],
    },
    fields: {
      type: Array,
      required: true,
    },
    fieldOptions: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    selectedRows: {
      type: Array,
      required: false,
      default: () => [],
    },
    showHoveredRow: {
      type: Boolean,
      required: false,
      default: false,
    },
    canAddRow: {
      type: Boolean,
      required: false,
      default: false,
    },
    showRowId: {
      type: Boolean,
      required: false,
      default: false,
    },
    fullHeight: {
      type: Boolean,
      required: false,
      default: false,
    },
    withFooter: {
      type: Boolean,
      required: false,
      default: false,
    },
    border: {
      type: Boolean,
      required: false,
      default: false,
    },
    multiple: {
      type: Boolean,
      required: false,
      default: false,
    },
    resizeFields: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      addRowHover: false,
      currentHoveredRow: null,
      fieldWidthOverride: {},
    }
  },
  computed: {
    fieldTypes() {
      return this.$registry.getAll('field')
    },
    orderedFixedFields() {
      const fixedFields = this.fixedFields.slice()
      return fixedFields.sort(sortFieldsByOrderAndIdFunction(this.fieldOptions))
    },
    visibleOrderedFields() {
      return this.fields
        .filter(filterVisibleFieldsFunction(this.fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(this.fieldOptions))
    },
    GRID_VIEW_MIN_FIELD_WIDTH() {
      return GRID_VIEW_MIN_FIELD_WIDTH
    },
  },
  mounted() {
    const keydownEvent = (event) => {
      if (
        // If we allow row hovering, we also want to allow keyboard navigation.
        this.showHoveredRow &&
        // Check if the user has hit either of the keys we care about. If not,
        // ignore.
        (event.key === 'ArrowUp' || event.key === 'ArrowDown')
      ) {
        // Prevent scrolling up and down while pressing the up and down key.
        event.stopPropagation()
        event.preventDefault()
        this.handleUpAndDownArrowPress(event)
      }
      // Allow the Enter key to select the value that is currently being hovered
      // over.
      if (
        this.showHoveredRow &&
        this.currentHoveredRow &&
        event.key === 'Enter'
      ) {
        event.preventDefault()
        event.stopPropagation()
        const row = this.rows.find((row) => row.id === this.currentHoveredRow)
        if (row) {
          this.$emit('row-click', row)
        }
      }
    }
    document.body.addEventListener('keydown', keydownEvent)
    this.$once('hide', () => {
      document.body.removeEventListener('keydown', keydownEvent)
    })
  },
  methods: {
    getHorizontalScrollbarElement() {
      return this.$refs.right
    },
    /**
     * Event that is called when the users does any form of scrolling on the whole grid
     * surface.
     */
    scroll(pixelY, pixelX) {
      const left = this.$refs.right.scrollLeft + pixelX
      this.horizontalScroll(left)
      this.$refs.scrollbars.update()
      return pixelY !== 0
    },
    horizontalScroll(left) {
      this.$refs.right.scrollLeft = left
    },
    handleUpAndDownArrowPress(event) {
      const isArrowUp = event.key === 'ArrowUp'
      let index = this.rows.findIndex((item) =>
        _.isEqual(item.id, this.currentHoveredRow)
      )
      if (index === -1) {
        // Selects the first or last row if no row was hovered before.
        index = isArrowUp ? this.rows.length - 1 : 0
      } else {
        // Selects the previous or next row if a row was in hover state before.
        index = isArrowUp ? index - 1 : index + 1
      }
      const next = this.rows[index]
      if (next) {
        this.currentHoveredRow = next.id
      }
    },
    getFieldWidth(field) {
      return (
        this.fieldWidthOverride[field.id] ||
        this.fieldOptions[field.id]?.width ||
        150
      )
    },
    moveFieldWidth(field, width) {
      // Temporarily set the field width override for the visual resize animation.
      this.$set(this.fieldWidthOverride, field.id, width)
    },
    updateFieldWidth(field, { width, oldWidth }) {
      this.fieldWidthOverride = {}
      this.$emit('update-field-width', { field, width, oldWidth })
    },
  },
}
</script>
