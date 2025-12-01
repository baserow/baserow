<template>
  <div class="gallery-view">
    <ButtonFloating
      v-if="
        !readOnly &&
        // Can't create rows in a table data sync table.
        (!table.data_sync || table.data_sync.two_way_sync) &&
        ($hasPermission(
          'database.table.create_row',
          table,
          database.workspace.id
        ) ||
          $hasPermission(
            'database.table.view.create_row',
            view,
            database.workspace.id
          ))
      "
      icon="iconoir-plus"
      position="fixed"
      @click="$refs.rowCreateModal.show()"
    >
    </ButtonFloating>
    <div
      ref="scroll"
      v-auto-scroll="{
        enabled: () => dragAndDropDraggingRow !== null,
        speed: 5,
        padding: 20,
      }"
      class="gallery-view__scroll"
    >
      <div
        class="gallery-view__cards"
        :class="{
          'gallery-view__cards--dragging': dragAndDropDraggingRow !== null,
        }"
        :style="{
          height: height + 'px',
        }"
      >
        <RowCard
          v-for="slot in buffer"
          v-show="slot.item !== undefined"
          :key="'card-' + slot.id"
          :fields="cardFields"
          :row="slot.item || {}"
          :workspace-id="database.workspace.id"
          :loading="slot.item === null"
          :cover-image-field="coverImageField"
          :decorations-by-place="decorationsByPlace"
          class="gallery-view__card"
          :style="{
            width: cardWidth + 'px',
            height: slot.item === null ? cardHeight + 'px' : undefined,
            transform: `translateX(${slot.position.left || 0}px) translateY(${
              slot.position.top || 0
            }px)`,
          }"
          :class="{
            'gallery-view__card--dragging': slot.item && slot.item._.dragging,
          }"
          @mousedown="
            rowDown(
              $event,
              slot.item,
              readOnly ||
                !$hasPermission(
                  'database.table.move_row',
                  table,
                  database.workspace.id
                )
            )
          "
          @mousemove="rowMoveOver($event, slot.item)"
          @mouseenter="rowMoveOver($event, slot.item)"
        ></RowCard>
      </div>
    </div>
    <RowCreateModal
      v-if="
        !readOnly &&
        ($hasPermission(
          'database.table.create_row',
          table,
          database.workspace.id
        ) ||
          $hasPermission(
            'database.table.view.create_row',
            view,
            database.workspace.id
          ))
      "
      ref="rowCreateModal"
      :database="database"
      :table="table"
      :view="view"
      :primary-is-sortable="true"
      :visible-fields="cardFields"
      :hidden-fields="hiddenFields"
      :show-hidden-fields="showHiddenFieldsInRowModal"
      :all-fields-in-table="fields"
      @toggle-hidden-fields-visibility="
        showHiddenFieldsInRowModal = !showHiddenFieldsInRowModal
      "
      @created="createRow"
      @order-fields="orderFields"
      @toggle-field-visibility="toggleFieldVisibility"
      @field-updated="$emit('refresh', $event)"
      @field-deleted="$emit('refresh')"
    ></RowCreateModal>
    <RowEditModal
      ref="rowEditModal"
      enable-navigation
      :database="database"
      :table="table"
      :view="view"
      :all-fields-in-table="fields"
      :primary-is-sortable="true"
      :visible-fields="cardFields"
      :hidden-fields="hiddenFields"
      :rows="allRows"
      :read-only="
        readOnly ||
        (!$hasPermission(
          'database.table.update_row',
          table,
          database.workspace.id
        ) &&
          !$hasPermission(
            'database.table.view.update_row',
            view,
            database.workspace.id
          ))
      "
      :show-hidden-fields="showHiddenFieldsInRowModal"
      @hidden="$emit('selected-row', undefined)"
      @toggle-hidden-fields-visibility="
        showHiddenFieldsInRowModal = !showHiddenFieldsInRowModal
      "
      @update="updateValue"
      @order-fields="orderFields"
      @toggle-field-visibility="toggleFieldVisibility"
      @field-updated="$emit('refresh', $event)"
      @field-deleted="$emit('refresh')"
      @field-created="showFieldCreated"
      @field-created-callback-done="afterFieldCreatedUpdateFieldOptions"
      @navigate-previous="$emit('navigate-previous', $event, activeSearchTerm)"
      @navigate-next="$emit('navigate-next', $event, activeSearchTerm)"
      @refresh-row="refreshRow"
    >
    </RowEditModal>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'
import { mapGetters } from 'vuex'
import ResizeObserver from 'resize-observer-polyfill'

import { notifyIf } from '@baserow/modules/core/utils/error'
import { getCardHeight } from '@baserow/modules/database/utils/card'
import {
  recycleSlots,
  orderSlots,
} from '@baserow/modules/database/utils/virtualScrolling'
import {
  sortFieldsByOrderAndIdFunction,
  filterVisibleFieldsFunction,
  filterHiddenFieldsFunction,
} from '@baserow/modules/database/utils/view'
import RowCard from '@baserow/modules/database/components/card/RowCard'
import RowCreateModal from '@baserow/modules/database/components/row/RowCreateModal'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal'
import bufferedRowsDragAndDrop from '@baserow/modules/database/mixins/bufferedRowsDragAndDrop'
import viewHelpers from '@baserow/modules/database/mixins/viewHelpers'
import viewDecoration from '@baserow/modules/database/mixins/viewDecoration'
import { populateRow } from '@baserow/modules/database/store/view/grid'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'GalleryView',
  components: { RowCard, RowCreateModal, RowEditModal },
  mixins: [viewHelpers, bufferedRowsDragAndDrop, viewDecoration],
  props: {
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      gutterSize: 30,
      minimumCardWidth: 280,
      height: 0,
      cardWidth: 0,
      buffer: [],
      showHiddenFieldsInRowModal: false,
      dragAndDropCloneClass: 'gallery-view__card--dragging-clone',
    }
  },
  computed: {
    ...mapGetters({
      row: 'rowModalNavigation/getRow',
    }),
    firstRows() {
      return this.allRows.slice(0, 200)
    },
    /**
     * In order for the virtual scrolling to work, we need to know what the height of
     * the card is to correctly position it.
     */
    cardHeight() {
      return getCardHeight(
        this.cardFields,
        this.coverImageField,
        this.$registry
      )
    },
    /**
     * Returns the visible field objects in the right order.
     */
    cardFields() {
      const fieldOptions = this.fieldOptions
      return this.fields
        .filter(filterVisibleFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    hiddenFields() {
      const fieldOptions = this.fieldOptions
      return this.fields
        .filter(filterHiddenFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    coverImageField() {
      const fieldId = this.view.card_cover_image_field
      return this.fields.find((field) => field.id === fieldId) || null
    },
    activeSearchTerm() {
      return this.$store.getters[
        `${this.storePrefix}view/gallery/getActiveSearchTerm`
      ]
    },
  },
  watch: {
    cardHeight() {
      this.$nextTick(() => {
        this.updateBuffer(true, false)
      })
    },
    allRows() {
      this.$nextTick(() => {
        this.updateBuffer(true, false)
      })
    },
    row: {
      deep: true,
      handler(row, oldRow) {
        if (this.$refs.rowEditModal) {
          if (
            (oldRow === null && row !== null) ||
            (oldRow && row && oldRow.id !== row.id)
          ) {
            this.populateAndEditRow(row)
          } else if (oldRow !== null && row === null) {
            // Pass emit=false as argument into the hide function because that will
            // prevent emitting another `hidden` event of the `RowEditModal` which can
            // result in the route changing twice.
            this.$refs.rowEditModal.hide(false)
          }
        }
      },
    },
  },
  mounted() {
    this.updateBuffer()
    this.$el.resizeObserver = new ResizeObserver(() => {
      this.updateBuffer()
    })
    this.$el.resizeObserver.observe(this.$el)

    const fireUpdateBuffer = {
      last: Date.now(),
      distance: 0,
    }

    // Debounce function that's called when the user scrolls really fast. This is to
    // make sure that the `updateBuffer` method is called with the
    // `dispatchVisibleRows` parameter to true when the user immediately stops
    // scrolling fast.
    const updateBufferDebounced = debounce(() => {
      this.updateBuffer(true, false)
    }, 100)

    // This debounced function is called when the user stops scrolling.
    const updateOrderDebounced = debounce(() => {
      this.updateBuffer(false, true)
    }, 110)

    this.$el.scrollEvent = (event) => {
      // Call the update order debounce function to simulate a stop scrolling event.
      updateOrderDebounced()

      const now = Date.now()
      const { scrollTop } = event.target

      const distance = Math.abs(scrollTop - fireUpdateBuffer.distance)
      const timeDelta = now - fireUpdateBuffer.last

      if (timeDelta > 100) {
        const velocity = distance / timeDelta

        fireUpdateBuffer.last = now
        fireUpdateBuffer.distance = scrollTop

        if (velocity < 2.5) {
          // When scrolling "slow", the dispatchVisibleRows parameter is true so that
          // the visible rows are fetched if needed.
          updateBufferDebounced.cancel()
          this.updateBuffer(true, false)
        } else {
          // Check if the user is scrolling super fast because in that case we don't
          // fetch the rows when they're not needed.
          updateBufferDebounced()
          this.updateBuffer(false, false)
        }
      } else {
        // If scroll stopped within the 100ms we still want to have a last
        // updateBuffer(true) call.
        updateBufferDebounced()
        this.updateBuffer(false, false)
      }
    }
    this.$refs.scroll.addEventListener('scroll', this.$el.scrollEvent)

    if (this.row !== null) {
      this.populateAndEditRow(this.row)
    }
  },
  beforeDestroy() {
    this.$el.resizeObserver.unobserve(this.$el)
    this.$refs.scroll.removeEventListener('scroll', this.$el.scrollEvent)
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        allRows: this.$options.propsData.storePrefix + 'view/gallery/getRows',
        fieldOptions:
          this.$options.propsData.storePrefix +
          'view/gallery/getAllFieldOptions',
      }),
    }
  },
  methods: {
    getDragAndDropStoreName(props) {
      return `${props.storePrefix}view/gallery`
    },
    /**
     * This method makes sure that the correct cards/rows are shown based on the
     * scroll offset, viewport width, viewport height and card height. Based on these
     * values we can calculate which how many rows should be visible, which ones are
     * visible and what their position is without rendering all the rows in the store
     * at once.
     *
     * @param dispatchVisibleRows Indicates whether we want to dispatch the visibleRows
     *  action in the store. In some cases, when scrolling really fast through data we
     *  might want to wait a small moment before calling the action, which will make a
     *  request to the backend if needed.
     */
    updateBuffer(dispatchVisibleRows = true, updateOrder = true) {
      const el = this.$refs.scroll

      const gutterSize = this.gutterSize
      const containerWidth = el.clientWidth
      const containerHeight = el.clientHeight

      const cardsPerRow = Math.min(
        Math.max(Math.floor(containerWidth / this.minimumCardWidth), 1),
        20
      )
      const cardHeight = this.cardHeight
      const cardWidth = (containerWidth - gutterSize) / cardsPerRow - gutterSize
      const totalRows = Math.ceil(this.allRows.length / cardsPerRow)
      const height = totalRows * (cardHeight + gutterSize) + gutterSize

      this.cardWidth = cardWidth
      this.height = height

      const scrollTop = el.scrollTop
      const minimumCardsToRender =
        (Math.ceil(containerHeight / (cardHeight + gutterSize)) + 1) *
        cardsPerRow
      const startIndex =
        Math.floor(scrollTop / (cardHeight + gutterSize)) * cardsPerRow
      const endIndex = startIndex + minimumCardsToRender
      const visibleRows = this.allRows.slice(startIndex, endIndex)

      const getPosition = (row, positionInVisible) => {
        const positionInAll = startIndex + positionInVisible
        return {
          left:
            gutterSize +
            (positionInAll % cardsPerRow) * (gutterSize + cardWidth),
          top:
            gutterSize +
            Math.floor(positionInAll / cardsPerRow) * (gutterSize + cardHeight),
        }
      }
      recycleSlots(this.buffer, visibleRows, getPosition, minimumCardsToRender)

      if (updateOrder) {
        orderSlots(this.buffer, visibleRows)
      }

      if (dispatchVisibleRows) {
        // Tell the store which rows/cards are visible so that it can fetch the missing
        // ones if needed.
        this.$store.dispatch(
          this.storePrefix + 'view/gallery/fetchMissingRowsInNewRange',
          {
            startIndex,
            endIndex,
          }
        )
      }
    },
    async createRow({ row, callback }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/gallery/createNewRow',
          {
            view: this.view,
            table: this.table,
            fields: this.fields,
            values: row,
          }
        )
        callback()
      } catch (error) {
        callback(error)
      }
    },
    async updateValue({ field, row, value, oldValue }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/gallery/updateRowValue',
          {
            table: this.table,
            view: this.view,
            fields: this.fields,
            row,
            field,
            value,
            oldValue,
          }
        )
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
    /**
     * Is called when the user clicks on the card but did not move it to another
     * position.
     */
    rowClick(row) {
      this.$refs.rowEditModal.show(row.id)
      this.$emit('selected-row', row)
    },
    /**
     * Calls action in the store to refresh row directly from the backend - f. ex.
     * when editing row from a different table, when editing is complete, we need
     * to refresh the 'main' row that's 'under' the RowEdit modal.
     */
    refreshRow(row) {
      if (this.refreshingRow) {
        return
      }
      this.refreshingRow = true

      this.$nextTick(async () => {
        try {
          await this.$store.dispatch(
            this.storePrefix + 'view/gallery/refreshRowFromBackend',
            { table: this.table, row }
          )
        } catch (error) {
          notifyIf(error, 'row')
        } finally {
          this.refreshingRow = false
        }
      })
    },
    /**
     * Calls the fieldCreated callback and shows the hidden fields section
     * because new fields are hidden by default.
     */
    showFieldCreated({ fetchNeeded, ...context }) {
      this.fieldCreated({ fetchNeeded, ...context })
      this.showHiddenFieldsInRowModal = true
    },
    /**
     * Populates a new row and opens the row edit modal
     * to edit the row.
     */
    populateAndEditRow(row) {
      const rowClone = populateRow(clone(row))
      this.$refs.rowEditModal.show(row.id, rowClone)
    },
  },
}
</script>
