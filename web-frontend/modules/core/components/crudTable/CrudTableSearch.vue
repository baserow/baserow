<template>
  <form @submit.prevent="doSearch(headerSearchTerm, true)">
    <FormInput
      ref="searchInput"
      v-model="headerSearchTerm"
      size="large"
      :placeholder="$t('crudTableSearch.search')"
      icon-left="iconoir-search"
      :loading="loading"
      @input="doSearch($event, false)"
    >
    </FormInput>
  </form>
</template>

<script>
import debounce from 'lodash/debounce'

/**
 * Will emit a `search-changed` event with the event object being the string of the
 * users search term. Takes a `loading` prop which will cause the search to display in
 * a loading state, it is upto the parent to set this when reacting to the
 * `searched-changed` event.
 *
 * This event is debounced internally so it will only be emitted after the user has
 * stopped typing for a short period of time, this way the component reacting to search
 * will not be spammed by an event for every single key press.
 */
export default {
  name: 'CrudTableSearch',
  props: {
    loading: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['close-modals', 'search-changed'],
  data: () => {
    return {
      headerSearchTerm: '',
      searchDebounce: null,
    }
  },
  mounted() {
    this.$priorityBus.$on(
      'start-search',
      this.$priorityBus.level.LOW,
      this.searchStarted
    )
  },
  beforeUnmount() {
    this.$priorityBus.$off('start-search', this.searchStarted)
  },
  methods: {
    keydown(event) {
      if (event.key !== 'Enter') {
        this.doSearch(this.headerSearchTerm, false)
      }
    },
    searchStarted({ event }) {
      event.preventDefault()
      this.$bus.$emit('close-modals')
      this.$refs.searchInput.focus()
    },
    doSearch(query, immediate) {
      const search = () => {
        this.$emit('search-changed', query)
      }
      if (this.searchDebounce) {
        this.searchDebounce.cancel()
      }
      if (immediate) {
        search()
      } else {
        this.searchDebounce = debounce(search, 400)
        this.searchDebounce()
      }
    },
  },
}
</script>
