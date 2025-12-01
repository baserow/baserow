import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  props: {
    row: {
      type: Object,
      required: true,
    },
    value: {
      type: Array,
      required: true,
    },
  },
  computed: {
    shouldFetchRow() {
      return (
        this.value?.length === LINKED_ITEMS_DEFAULT_LOAD_COUNT &&
        !this.row._?.fullyLoaded
      )
    },
    isFetchingRow() {
      return this.row._?.fetching ?? false
    },
  },
  watch: {
    row: {
      handler() {
        if (this.shouldFetchRow && !this.isFetchingRow) {
          this.$emit('refresh-row')
        }
      },
      immediate: true,
    },
  },
}
