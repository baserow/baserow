<template>
  <Context ref="context">
    <div
      class="calendar-month-day-expanded"
      :style="{
        height: contextHeight + 'px',
        width: Math.max(parentWidth + 16, 212) + 'px',
      }"
    >
      <div class="calendar-month-day-expanded__title">
        {{ label }}
        <div class="calendar-month-day-expanded__close" @click="hide">
          <i class="iconoir-cancel"></i>
        </div>
      </div>
      <InfiniteScroll
        ref="scroll"
        :max-count="count"
        :current-count="rows.length"
        :loading="loading"
        :render-end="false"
        class="calendar-month-day-expanded__cards"
        :style="{
          height: innerHeight + 'px',
        }"
        @load-next-page="fetch('scroll')"
      >
        <template #default>
          <CalendarCard
            v-for="(row, index) in rows"
            :key="row.id"
            :row="row"
            :fields="fields"
            :store-prefix="storePrefix"
            :class="{ last: index == rows.length - 1 }"
            :parent-width="contextWidth"
            :decorations-by-place="decorationsByPlace"
            v-on="$listeners"
          >
          </CalendarCard>
          <div v-if="error" class="calendar-month-day-expanded__try-again">
            <a @click="fetch('click')">
              {{ $t('calendarMonthDayExpanded.tryAgain') }}
              <i class="iconoir-refresh-double"></i>
            </a>
          </div>
        </template>
      </InfiniteScroll>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import CalendarCard from '@baserow_premium/components/views/calendar/CalendarCard'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'CalendarMonthDayModalExpanded',
  components: {
    CalendarCard,
    InfiniteScroll,
  },
  mixins: [context],
  props: {
    day: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
    parentWidth: {
      type: Number,
      required: true,
    },
    parentHeight: {
      type: Number,
      required: true,
    },
    decorationsByPlace: {
      type: Object,
      required: false,
      default: () => undefined,
    },
  },
  data() {
    return {
      error: false,
      loading: false,
    }
  },
  computed: {
    label() {
      return this.day.date.format('dddd, MMMM D')
    },
    dayStack() {
      const dayStack = this.$store.getters[
        this.storePrefix + 'view/calendar/getDateStack'
      ](this.day.dateString)
      return dayStack || { results: [], count: 0 }
    },
    rows() {
      return this.dayStack.results
    },
    count() {
      return this.dayStack.count
    },
    cardHeight() {
      return 28
    },
    contextHeight() {
      const minHeight = this.parentHeight + 4
      const heightCards = this.allCardsHeight
      const maxHeight = this.maxContextHeight
      if (heightCards < minHeight) {
        return minHeight
      }
      if (heightCards < maxHeight) {
        return heightCards
      }
      return Math.max(maxHeight, 200)
    },
    allCardsHeight() {
      return 50 + this.cardHeight * this.count + 14
    },
    fetchedCardsHeight() {
      return 50 + this.cardHeight * this.rows.length + 14
    },
    maxContextHeight() {
      return this.parentHeight * 2 - 10
    },
    contextWidth() {
      return this.$refs.context.$el.clientWidth
    },
    innerHeight() {
      return this.contextHeight - 48
    },
  },
  methods: {
    async show(...args) {
      this.getRootContext().show(...args)
      if (
        this.rows.length !== this.count &&
        this.fetchedCardsHeight < this.maxContextHeight
      ) {
        await this.fetchInitial()
      }
    },
    async fetchInitial() {
      await this.fetch('scroll')
    },
    async fetch(type) {
      if (this.error && type === 'scroll') {
        return
      }

      this.error = false
      this.loading = true

      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/calendar/fetchMore',
          {
            date: this.day.dateString,
            fields: this.fields,
          }
        )
      } catch (error) {
        this.error = true
        notifyIf(error)
      }

      this.loading = false
    },
  },
}
</script>
