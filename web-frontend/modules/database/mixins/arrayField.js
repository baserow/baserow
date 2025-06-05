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
        !this.row._?.fetched
      )
    },
  },
  mounted() {
    if (this.shouldFetchRow && !this.row._?.fetching) {
      this.$emit('refresh-row')
    }
  },
}
