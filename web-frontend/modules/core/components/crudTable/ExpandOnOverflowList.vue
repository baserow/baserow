<template>
  <div class="expand-overflow-list" v-on="$attrs">
    <div class="expand-overflow-list__container">
      <span v-if="noRecords"><slot name="no-records"></slot></span>
      <span ref="empty" class="expand-overflow-list__empty-item"></span>
      <span
        v-for="(record, index) in records"
        ref="records"
        :key="'overflow-row-record' + record.id + '-' + index"
        class="expand-overflow-list__item"
        :style="{
          order: index,
        }"
      >
        {{ record[nameKey] }}
        <slot name="icon" :record="record"></slot>
      </span>
      <a
        v-show="overflowing"
        ref="expand"
        class="expand-overflow-list__expand"
        :style="{
          order: expandOrder,
        }"
        @click.prevent="showHiddenContext"
        >+{{ numHiddenRecords }}</a
      >
      <ExpandOnOverflowHiddenContext
        ref="hiddenContext"
        :name-key="nameKey"
        :hidden-records="hiddenRecords"
      ></ExpandOnOverflowHiddenContext>
    </div>
  </div>
</template>

<script>
import ExpandOnOverflowHiddenContext from '@baserow/modules/core/components/crudTable/ExpandOnOverflowHiddenContext'

/**
 * Displays a list of a records with a modal displaying any records that do not fit.
 */
export default {
  name: 'ExpandOnOverflowList',
  components: {
    ExpandOnOverflowHiddenContext,
  },
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
    nameKey: {
      required: false,
      type: String,
      default: 'name',
    },
  },
  data() {
    return {
      overflowing: false,
      numHiddenRecords: 0,
      renderContext: false,
      expandOrder: -1,
    }
  },
  computed: {
    noRecords() {
      return this.records.length === 0
    },
    hiddenRecords() {
      return this.records.slice(this.records.length - this.numHiddenRecords)
    },
    records() {
      return this.row[this.column.key]
    },
    getId() {
      return this.row.id
    },
  },
  mounted() {
    this.$el.resizeObserver = new ResizeObserver(this.recalculateHiddenRecords)
    this.$el.resizeObserver.observe(this.$el)
  },
  beforeUnmount() {
    this.$el.resizeObserver.disconnect()
  },
  created() {
    this.recalculateHiddenRecords()
  },
  methods: {
    showHiddenContext(event) {
      this.$refs.hiddenContext.show(event.currentTarget, 'bottom', 'left', 4)
    },
    /**
     * Calculates how many records fit into the records cell, if any are overflowing and
     * do not fit we add a + button to display a context menu showing these hidden
     * records. We rely on flexbox wrapping to make records which do not fit in the cell
     * wrap down to a new row below which is invisible.
     */
    recalculateHiddenRecords() {
      if (import.meta.server) {
        return
      }

      this.$nextTick(() => {
        let expandOrder = 0
        let numHiddenRecords = this.records.length

        if (!this.$refs.empty) {
          return
        }

        /*
           The starting empty element never flex-wraps down into a new row as it has 0
           width.
           If an element after it has the same top value then it must not have wrapped
           down and hence must fit and be visible. If the elements top value is greater
           then it must have overflowed and wrapped into a row below, causing it to
           become invisible.
           Comparing top values is done instead of trying to
           manually calculate which records fit using el.client/scrollWidth because:
           1. We don't want to worry about exactly calculating the widths of each record
              as there are possibly bugs with this in Vue (scrollWidth etc can return
              invalid numbers in some unknown situations).
           2. By using the tops we leave it entirely up to CSS and the DOM to figure out
              what fits or not reducing the complexity of this method. We don't want
              to try and replicate the overflow calculations ourselves as then we need
              to maintain code that matches the browser calculation in every possible
              situation.
          */
        const emptyElementTop = this.$refs.empty.getBoundingClientRect().top

        // The records will be null when the user has no records.
        if (this.$refs.records) {
          for (let i = 0; i < this.$refs.records.length; i++) {
            const recordEl = this.$refs.records[i]
            const recordTop = recordEl.getBoundingClientRect().top
            if (recordTop > emptyElementTop) {
              /*
               This recordEl element has been flex-wrapped down into a new row due to no
               space. Every record after this one must also be hidden hence we now have
               calculated the number of hidden records and can break.

               Insert the expand button before this hidden record. This button might also
               wrap down and become invisible hence we later on recheck if this has
               happened or not.
              */
              expandOrder = i - 1
              break
            } else {
              // Insert the expand button after the latest visible record
              expandOrder = i
              numHiddenRecords--
            }
          }
        }

        this.expandOrder = expandOrder
        this.numHiddenRecords = numHiddenRecords
        this.overflowing = numHiddenRecords !== 0

        /*
           Check that the expand button hasn't wrapped down and become invisible because
           there wasn't enough room to fit it on the first row. If so move it back one
           further in the order so it replaces the last visible record in the row instead
          */
        if (this.overflowing) {
          /*
             We have to wait a tick for the DOM to recalculate to see if the inserted
             expand button fits or not. This is much easier, simpler and cleaner
             than attempting to do the calculation CSS/DOM will do for us ourselves!
            */
          this.$nextTick(() => {
            const emptyElementTop = this.$refs.empty.getBoundingClientRect().top
            const expandTop = this.$refs.expand.getBoundingClientRect().top
            if (expandTop > emptyElementTop) {
              this.expandOrder--
              // By moving the button back one we will make the last record overflow,
              // wrap and become invisible so we update numHiddenTeams accordingly.
              this.numHiddenRecords++
            }
          })
        }
      })
    },
  },
}
</script>
