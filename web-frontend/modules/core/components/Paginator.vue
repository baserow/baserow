<template>
  <div class="paginator">
    <!-- <div class="paginator__name"></div> -->

    <a
      class="paginator__button"
      :class="{
        'paginator__button--disabled': page === 1,
      }"
      @click="changePage(page - 1)"
    >
      <i class="iconoir-nav-arrow-left"></i>
    </a>

    <div class="paginator__content">
      <span>{{ $t('paginator.page') }}</span>
      <input
        type="text"
        class="paginator__content-input"
        required
        :size="totalPages.toString().length"
        :value="page"
        @change="changePageFromInput($event)"
        @keydown.enter.prevent="changePageFromInput($event)"
      />
      <span>{{ $t('paginator.of', { pages: totalPages }) }}</span>
    </div>

    <a
      class="paginator__button"
      :class="{
        'paginator__button--disabled': page === totalPages,
      }"
      @click="changePage(page + 1)"
    >
      <i class="iconoir-nav-arrow-right"></i>
    </a>
  </div>
</template>
<script>
export default {
  name: 'Paginator',
  props: {
    /**
     * The total number of pages available.
     */
    totalPages: {
      type: Number,
      default: 0,
      validator: (prop) => typeof prop === 'number' || prop === null,
    },
    /**
     * The currently selected page.
     */
    page: {
      type: Number,
      default: 0,
    },
  },
  emits: ['change-page'],
  methods: {
    changePageFromInput(event) {
      this.changePage(Number(event.target.value))
      event.target.value = this.page
    },
    changePage(newPage) {
      if (
        Number.isInteger(newPage) &&
        newPage !== this.page &&
        newPage <= this.totalPages &&
        newPage > 0
      )
        this.$emit('change-page', newPage)
    },
  },
}
</script>
