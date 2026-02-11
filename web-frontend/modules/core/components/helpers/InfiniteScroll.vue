<template>
  <section
    ref="infiniteScroll"
    :class="{ 'infinite-scroll--reversed': reverse }"
    class="infinite-scroll"
    @scroll="handleScroll"
    v-on="$attrs"
  >
    <slot />
    <div
      v-show="hasMore"
      ref="loadingWrapper"
      class="infinite-scroll__loading-wrapper"
    >
      <div v-if="loading" class="loading"></div>
    </div>
    <slot v-if="renderEnd && !hasMore && wrapperHasScrollbar" name="end">
      <div class="infinite-scroll__end-line"></div>
    </slot>
  </section>
</template>

<script>
/**
 * The InfiniteScroll component is designed to wrap a list paginated list of items.
 * Provide it with the currentCount of loaded items and the maxCount that is available
 * from the server and it will emit 'load-next-page' events when the user scrolls to
 * the end of the current items.
 *
 * If the maxCount is not available, the hasMore prop should be used to indicate
 * whether to load the next page.
 * Both maxCount and hasMore are mutually exclusive, meaning only one of them should
 * be set.
 *
 * If reverse is set then the list of items is rendered bottom to top and when the user
 * scrolls to the top the next page is loaded.
 *
 * Provide an end slot which will be shown when the user scrolls to the end of all
 * available items.
 */
export default {
  props: {
    currentCount: {
      type: Number,
      required: true,
    },
    maxCount: {
      type: Number,
      required: false,
      default: 0,
    },
    hasMorePage: {
      type: Boolean,
      required: false,
      default: null,
    },
    pageSize: {
      type: Number,
      required: false,
      // Please keep in sync with the default page size in
      // backend/src/baserow/api/pagination.py
      default: 100,
    },
    loading: {
      type: Boolean,
      required: true,
    },
    reverse: {
      type: Boolean,
      required: false,
      default: false,
    },
    renderEnd: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  emits: ['load-next-page'],
  data() {
    return {
      // We don't want to show the end-line unless the user has scrolled somewhere and
      // hit the end. This also helps us properly align any end-line as it always has
      // a scrollbar and can be calculated as such.
      wrapperHasScrollbar: false,
    }
  },
  computed: {
    hasMore() {
      return this.hasMorePage !== null
        ? this.hasMorePage
        : this.currentCount < this.maxCount
    },
  },
  watch: {
    currentCount() {
      this.calculateIfWrapperHasScrollbar()
    },
  },
  created() {
    if (this.reverse) {
      // In reverse mode the start is actually the very bottom of the wrapper, so we
      // need to scroll there immediately.
      this.$nextTick(() => {
        this.scrollToStart()
      })
    }
    this.calculateIfWrapperHasScrollbar()
  },
  methods: {
    calculateIfWrapperHasScrollbar() {
      this.$nextTick(() => {
        const infiniteScroll = this.$refs.infiniteScroll
        this.wrapperHasScrollbar =
          infiniteScroll &&
          infiniteScroll.scrollHeight > infiniteScroll.clientHeight
      })
    },
    clientHeight() {
      return this.$el.clientHeight
    },
    /**
     * Action listener called when the scroll wrapper scrolls, triggers a load next
     * page event if the user has scrolled to the end of the wrapper.
     */
    handleScroll({ target: { scrollTop, clientHeight, scrollHeight } }) {
      const loadingWrapperHeight = this.$refs.loadingWrapper?.clientHeight || 0
      const height = clientHeight + loadingWrapperHeight
      if (this.reverse) {
        if (-scrollTop + height >= scrollHeight) {
          this.loadNextPage()
        }
      } else if (scrollTop + height >= scrollHeight) {
        this.loadNextPage()
      }
    },
    /**
     * Emits a load-next-page event if there are still things to load in from the server
     * and we aren't already loading.
     */
    loadNextPage() {
      if (this.hasMore && !this.loading) {
        const nextPage = Math.ceil(this.currentCount / this.pageSize) + 1
        this.$emit('load-next-page', nextPage)
      }
    },
    scrollToStart() {
      const infiniteScroll = this.$refs.infiniteScroll
      infiniteScroll.scrollTop = this.reverse ? 0 : infiniteScroll.scrollHeight
    },
  },
}
</script>
