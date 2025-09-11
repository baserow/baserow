<template>
  <div
    ref="wrapper"
    v-auto-scroll="{
      enabled: () => draggingRow !== null,
      speed: 3,
      padding: 24,
      scrollElement: () => $refs.scroll.$el,
    }"
    class="kanban-view__stack-wrapper"
    @mouseleave.stop="wrapperMouseLeave"
  >
    <div
      class="kanban-view__stack"
      :class="{ 'kanban-view__stack--dragging': draggingRow !== null }"
      @mousemove="stackMoveOver($event, stack, id)"
    >
      <div class="kanban-view__stack-head">
        <div v-if="option === null" class="kanban-view__uncategorized">
          {{ $t('kanbanViewStack.uncategorized') }}
        </div>
        <template v-else>
          <!--<a v-if="!readOnly" href="#" class="kanban-view__drag"></a>-->
          <div class="kanban-view__option-wrapper">
            <div
              class="kanban-view__option"
              :class="'background-color--' + option.color"
            >
              {{ option.value }}
            </div>
          </div>
        </template>
        <div class="kanban-view__count">
          {{ stack.count }}
        </div>
        <a
          v-if="!readOnly && showStackContextMenu"
          ref="editContextLink"
          class="kanban-view__options"
          @click="
            $refs.editContext.toggle(
              $refs.editContextLink,
              'bottom',
              'right',
              -2
            )
          "
        >
          <i class="iconoir-nav-arrow-down"></i>
        </a>
        <KanbanViewStackContext
          v-if="!readOnly && showStackContextMenu"
          ref="editContext"
          :option="option"
          :database="database"
          :table="table"
          :view="view"
          :fields="fields"
          :single-select-field="singleSelectField"
          :store-prefix="storePrefix"
          @create-row="$emit('create-row', { option })"
          @refresh="$emit('refresh', $event)"
        ></KanbanViewStackContext>
      </div>
      <InfiniteScroll
        ref="scroll"
        :max-count="stack.count"
        :current-count="stack.results.length"
        :loading="loading"
        :render-end="false"
        class="kanban-view__stack-cards"
        @load-next-page="fetch('scroll')"
      >
        <template #default>
          <div
            :style="{ 'min-height': cardHeight * stack.results.length + 'px' }"
          >
            <RowCard
              v-for="slot in buffer"
              v-show="slot.position != -1"
              :key="'card-' + slot.id"
              :fields="cardFields"
              :decorations-by-place="decorationsByPlace"
              :row="slot.row"
              :workspace-id="database.workspace.id"
              :cover-image-field="coverImageField"
              :style="{
                transform: `translateY(${
                  slot.position * cardHeight + bufferTop
                }px)`,
              }"
              class="kanban-view__stack-card"
              :class="{
                'kanban-view__stack-card--dragging': slot.row._.dragging,
              }"
              @mousedown="cardDown($event, slot.row)"
              @mousemove="cardMoveOver($event, slot.row)"
              v-on="$listeners"
            ></RowCard>
          </div>
          <div v-if="error" class="margin-top-2">
            <a @click="fetch('click')">
              {{ $t('kanbanViewStack.tryAgain') }}
              <i class="iconoir-refresh-double"></i>
            </a>
          </div>
        </template>
      </InfiniteScroll>
      <div class="kanban-view__stack-foot">
        <ButtonFloating
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
          type="primary"
          icon="iconoir-plus"
          full-width
          :disabled="draggingRow !== null"
          @click="!readOnly && $emit('create-row', { option })"
        ></ButtonFloating>
      </div>
    </div>
    <!--
    <div class="kanban-view__stack-wrapper">
      <div class="kanban-view__collapsed-stack-wrapper">
        <a class="kanban-view__collapsed-stack">
          <div class="kanban-view__count">10 records</div>
          <div class="kanban-view__option-wrapper margin-right-0">
            <div class="kanban-view__option background-color--green">
              Idea
            </div>
          </div>
        </a>
      </div>
    </div>
    -->
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import kanbanViewHelper from '@baserow_premium/mixins/kanbanViewHelper'
import RowCard from '@baserow/modules/database/components/card/RowCard'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import { populateRow } from '@baserow_premium/store/view/kanban'
import KanbanViewStackContext from '@baserow_premium/components/views/kanban/KanbanViewStackContext'
import { getCardHeight } from '@baserow/modules/database/utils/card'
import viewDecoration from '@baserow/modules/database/mixins/viewDecoration'

export default {
  name: 'KanbanViewStack',
  components: { InfiniteScroll, RowCard, KanbanViewStackContext },
  mixins: [kanbanViewHelper, viewDecoration],
  props: {
    option: {
      validator: (prop) => typeof prop === 'object' || prop === null,
      required: false,
      default: null,
    },
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    cardFields: {
      type: Array,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      error: false,
      loading: false,
      buffer: [],
      bufferTop: 0,
      scrollHeight: 0,
      scrollTop: 0,
      // Contains an HTML DOM element copy of the card that's being dragged.
      copyElement: null,
      // The row object that's currently being down
      downCardRow: null,
      // The initial horizontal position absolute client position of the card after
      // mousedown.
      downCardClientX: 0,
      // The initial vertical position absolute client position of the card after
      // mousedown.
      downCardClientY: 0,
      // The autoscroll timeout that keeps keeps calling the autoScrollLoop method to
      // initiate the autoscroll effect when dragging a card.
      autoScrollTimeout: null,
    }
  },
  computed: {
    showStackContextMenu() {
      return (
        this.singleSelectField &&
        (this.$hasPermission(
          'database.table.create_row',
          this.table,
          this.database.workspace.id
        ) ||
          this.$hasPermission(
            'database.table.view.create_row',
            this.view,
            this.database.workspace.id
          ) ||
          this.$hasPermission(
            'database.table.field.update',
            this.singleSelectField,
            this.database.workspace.id
          ))
      )
    },
    /**
     * In order for the virtual scrolling to work, we need to know what the height of
     * the card is to correctly position it.
     */
    cardHeight() {
      // 10 = margin-bottom of kanban.scss.kanban-view__stack-card
      return (
        getCardHeight(this.cardFields, this.coverImageField, this.$registry) +
        10
      )
    },
    /**
     * Figure out what the stack id that's used in the store is. The representation is
     * slightly different there.
     */
    id() {
      return this.option === null ? 'null' : this.option.id.toString()
    },
    /**
     * Using option id received via the properties, we can get the related stack from
     * the store.
     */
    stack() {
      return this.$store.getters[this.storePrefix + 'view/kanban/getStack'](
        this.id
      )
    },
    coverImageField() {
      const fieldId = this.view.card_cover_image_field
      return this.fields.find((field) => field.id === fieldId) || null
    },
    singleSelectField() {
      return this.fields.find((field) => field.id === this.singleSelectFieldId)
    },
  },
  watch: {
    cardHeight() {
      this.$nextTick(() => {
        this.updateBuffer()
      })
    },
    'stack.results'() {
      this.$nextTick(() => {
        this.updateBuffer()
      })
    },
  },
  mounted() {
    this.updateBuffer()

    this.$el.resizeEvent = () => {
      this.updateBuffer()
    }
    this.$el.scrollEvent = () => {
      this.updateBuffer()
    }

    window.addEventListener('resize', this.$el.resizeEvent)
    this.$refs.scroll.$el.addEventListener('scroll', this.$el.scrollEvent)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.$el.resizeEvent)
    this.$refs.scroll.$el.removeEventListener('scroll', this.$el.scrollEvent)
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        draggingRow:
          this.$options.propsData.storePrefix + 'view/kanban/getDraggingRow',
        draggingOriginalStackId:
          this.$options.propsData.storePrefix +
          'view/kanban/getDraggingOriginalStackId',
        singleSelectFieldId:
          this.$options.propsData.storePrefix +
          'view/kanban/getSingleSelectFieldId',
      }),
    }
  },
  methods: {
    /**
     * Called when a user presses the left mouse on a card. This method will prepare
     * the dragging if the user moves the mouse a bit. Otherwise, if the mouse is
     * release without moving, the edit modal is opened.
     */
    cardDown(event, row) {
      // If it isn't a left click.
      if (event.button !== 0) {
        return
      }

      event.preventDefault()

      this.downCardRow = row
      this.$el.mouseUpEvent = (event) => this.cardUp(event)
      window.addEventListener('mouseup', this.$el.mouseUpEvent)

      if (
        !this.readOnly &&
        this.$hasPermission(
          'database.table.move_row',
          this.table,
          this.database.workspace.id
        )
      ) {
        const rect = event.target.getBoundingClientRect()
        this.downCardClientX = event.clientX
        this.downCardClientY = event.clientY
        this.downCardTop = event.clientY - rect.top
        this.downCardLeft = event.clientX - rect.left

        this.copyElement = document.createElement('div')
        this.copyElement.innerHTML = event.target.outerHTML
        this.copyElement.style = `position: absolute; left: 0; top: 0; width: ${rect.width}px; z-index: 10;`
        this.copyElement.firstChild.classList.add(
          'kanban-view__stack-card--dragging-copy'
        )

        this.$el.keydownEvent = (event) => {
          if (event.key === 'Escape') {
            if (this.draggingRow !== null) {
              this.$store.dispatch(
                this.storePrefix + 'view/kanban/cancelRowDrag',
                {
                  row: this.draggingRow,
                  originalStackId: this.draggingOriginalStackId,
                }
              )
            }
            this.cardCancel(event)
          }
        }
        document.body.addEventListener('keydown', this.$el.keydownEvent)

        this.$el.mouseMoveEvent = (event) => this.cardMove(event)
        window.addEventListener('mousemove', this.$el.mouseMoveEvent)

        this.cardMove(event)
      }
    },
    async cardMove(event) {
      if (this.draggingRow === null) {
        if (
          Math.abs(event.clientX - this.downCardClientX) > 3 ||
          Math.abs(event.clientY - this.downCardClientY) > 3
        ) {
          document.body.appendChild(this.copyElement)
          await this.$store.dispatch(
            this.storePrefix + 'view/kanban/startRowDrag',
            {
              row: this.downCardRow,
            }
          )
        }
      }

      this.copyElement.style.top = event.clientY - this.downCardTop + 'px'
      this.copyElement.style.left = event.clientX - this.downCardLeft + 'px'
    },
    async cardUp() {
      if (this.draggingRow !== null) {
        this.cardCancel()

        try {
          await this.$store.dispatch(
            this.storePrefix + 'view/kanban/stopRowDrag',
            {
              table: this.table,
              fields: this.fields,
            }
          )
        } catch (error) {
          notifyIf(error)
        }
      } else {
        this.$emit('edit-row', this.downCardRow)
        this.cardCancel()
      }
    },
    cardCancel() {
      this.downCardRow = null
      if (this.copyElement !== null) {
        this.copyElement.remove()
        this.copyElement = null
        document.body.removeEventListener('keydown', this.$el.keydownEvent)
        window.removeEventListener('mousemove', this.$el.mouseMoveEvent)
      }
      window.removeEventListener('mouseup', this.$el.mouseUpEvent)
    },
    async cardMoveOver(event, row) {
      if (
        this.draggingRow === null ||
        this.draggingRow.id === row.id ||
        !!event.target.transitioning
      ) {
        return
      }

      // If the field is read_only, it's not possible to move between stacks because
      // they would change the read_only value.
      const fieldType = this.$registry.get('field', this.singleSelectField.type)
      if (!fieldType.canWriteFieldValues(this.singleSelectField)) {
        const target = this.$store.getters[
          this.storePrefix + 'view/kanban/findStackIdAndIndex'
        ](row.id)
        if (target[0] !== this.draggingOriginalStackId) {
          return
        }
      }

      const rect = event.target.getBoundingClientRect()
      const top = event.clientY - rect.top
      const half = rect.height / 2
      const before = top <= half
      const moved = await this.$store.dispatch(
        this.storePrefix + 'view/kanban/forceMoveRowBefore',
        {
          row: this.draggingRow,
          targetRow: row,
          targetBefore: before,
        }
      )
      if (moved) {
        this.moved(event)
      }
    },
    /**
     * When dragging a row over an empty stack, we want to move that row into it.
     * Normally the row is only moved when it's being dragged over an existing card,
     * but it must also be possible drag a row into an empty stack that doesn't have
     * any cards.
     */
    async stackMoveOver(event, stack, id) {
      if (
        this.draggingRow === null ||
        stack.results.length > 0 ||
        !!event.target.transitioning
      ) {
        return
      }

      const moved = await this.$store.dispatch(
        this.storePrefix + 'view/kanban/forceMoveRowTo',
        {
          row: this.draggingRow,
          targetStackId: id,
          targetIndex: 0,
        }
      )
      if (moved) {
        this.moved(event)
      }
    },
    /**
     * After a row has been moved, we need to temporarily need to set the transition
     * state to true. While it's true, it can't be moved to another position to avoid
     * strange transition effects of other cards.
     */
    moved(event) {
      event.target.transitioning = true
      setTimeout(
        () => {
          event.target.transitioning = false
        },
        // Must be kept in sync with the transition-duration of
        // kanban.scss.kanban-view__stack--dragging
        100
      )
    },
    wrapperMouseLeave() {
      clearTimeout(this.autoScrollTimeout)
      this.autoScrollTimeout = null
    },
    updateBuffer() {
      const scroll = this.$refs.scroll
      const cardHeight = this.cardHeight
      const containerHeight = scroll.clientHeight()
      const scrollTop = scroll.$el.scrollTop
      const min = Math.ceil(containerHeight / cardHeight) + 2
      const rows = this.stack.results.slice(
        Math.floor(scrollTop / cardHeight),
        Math.ceil((scrollTop + containerHeight) / cardHeight)
      )
      this.bufferTop =
        rows.length > 0
          ? this.stack.results.findIndex((row) => row.id === rows[0].id) *
            cardHeight
          : 0

      // First fill up the buffer with the minimum amount of slots.
      for (let i = this.buffer.length; i < min; i++) {
        this.buffer.push({
          id: i,
          row: populateRow({ id: -1 }),
          position: -1,
        })
      }

      // Remove not needed slots.
      this.buffer = this.buffer.slice(0, min)

      // Check which rows are should not be displayed anymore and clear that slow
      // in the buffer.
      this.buffer.forEach((slot) => {
        const exists = rows.findIndex((row) => row.id === slot.row.id) >= 0
        if (!exists) {
          slot.row = populateRow({ id: -1 })
          slot.position = -1
        }
      })

      // Then check which rows should have which position.
      rows.forEach((row, position) => {
        // Check if the row is already in the buffer
        const index = this.buffer.findIndex((slot) => slot.row.id === row.id)

        if (index >= 0) {
          // If the row already exists in the buffer, then only update the position.
          this.buffer[index].position = position

          // If the row object has changed, it needs to be updated in the buffer in
          // order to maintain reactivity.
          if (this.buffer[index].row !== row) {
            this.buffer[index].row = row
          }
        } else {
          // If the row does not yet exists in the buffer, then we can find the first
          // empty slot and place it there.
          const emptyIndex = this.buffer.findIndex((slot) => slot.row.id === -1)
          this.buffer[emptyIndex].row = row
          this.buffer[emptyIndex].position = position
        }
      })
    },
    /**
     * Called when an additional set of rows must be fetched for this stack. This
     * typically happens when the user reaches the end of the card list.
     */
    async fetch(type) {
      if (this.error && type === 'scroll') {
        return
      }

      this.error = false
      this.loading = true

      try {
        await this.$store.dispatch(this.storePrefix + 'view/kanban/fetchMore', {
          selectOptionId: this.id,
        })
      } catch (error) {
        this.error = true
        notifyIf(error)
      }

      this.loading = false
    },
  },
}
</script>
