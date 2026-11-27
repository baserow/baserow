<template>
  <div>
    <a
      ref="contextLink"
      class="header__filter-link"
      :class="{
        'active active--success': view.filters.length > 0,
      }"
      @click="$refs.context.toggle($refs.contextLink, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon iconoir-filter"></i>
      <span class="header__filter-name">{{
        $t('viewFilter.filter', {
          count: view.filters.length,
        })
      }}</span>
    </a>
    <Context
      ref="context"
      class="filters"
      tabindex="-1"
      role="region"
      :aria-label="$t('viewFilter.filter', { count: view.filters.length })"
      :class="{ 'context--loading-overlay': view._.loading }"
      :horizontal-viewport-margin="8"
      max-height-if-outside-viewport
    >
      <ViewFilterForm
        :fields="fields"
        :view="view"
        :database="database"
        :is-public-view="isPublicView"
        :read-only="readOnly"
        :disable-filter="disableFilter"
        @changed="$emit('changed')"
      />
    </Context>
  </div>
</template>

<script>
import ViewFilterForm from '@baserow/modules/database/components/view/ViewFilterForm'

export default {
  name: 'ViewFilter',
  components: { ViewFilterForm },
  props: {
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    isPublicView: {
      type: Boolean,
      required: false,
      default: false,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    disableFilter: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['changed'],
  computed: {
    focusRequested() {
      return (
        !this.isPublicView &&
        this.$route.query.focus === 'filters' &&
        Number(this.$route.params.viewId) === this.view.id
      )
    },
  },
  watch: {
    focusRequested(requested) {
      if (requested) this.focusFilters()
    },
  },
  mounted() {
    if (this.focusRequested) this.focusFilters()
  },
  beforeMount() {
    this.$bus.$on('view-filter-created', this.filterCreated)
  },
  beforeUnmount() {
    this.$bus.$off('view-filter-created', this.filterCreated)
  },
  methods: {
    async focusFilters() {
      await this.$refs.context.show(this.$refs.contextLink, 'bottom', 'left', 4)
      if (!this.focusRequested) return
      const query = { ...this.$route.query }
      delete query.focus
      await this.$router.replace({
        path: this.$route.path,
        hash: this.$route.hash,
        query,
      })

      if (
        this.$refs.context?.open &&
        Number(this.$route.params.viewId) === this.view.id
      ) {
        this.$refs.context.getTeleportedElement()?.focus()
      }
    },
    /**
     * When a filter is created via an outside source we want to show the context menu.
     */
    filterCreated() {
      this.$refs.context.show(this.$refs.contextLink, 'bottom', 'left', 4)
    },
  },
}
</script>
