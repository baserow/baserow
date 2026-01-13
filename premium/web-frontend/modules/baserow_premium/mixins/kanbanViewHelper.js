import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  props: {
    storePrefix: {
      type: String,
      required: true,
    },
  },
  computed: {
    fieldOptions() {
      return this.$store.getters[
        `${this.storePrefix}view/kanban/getAllFieldOptions`
      ]
    },
    singleSelectFieldId() {
      return this.$store.getters[
        `${this.storePrefix}view/kanban/getSingleSelectFieldId`
      ]
    },
    allRows() {
      return this.$store.getters[`${this.storePrefix}view/kanban/getAllRows`]
    },
    draggingRow() {
      return this.$store.getters[
        `${this.storePrefix}view/kanban/getDraggingRow`
      ]
    },
    draggingOriginalStackId() {
      return this.$store.getters[
        `${this.storePrefix}view/kanban/getDraggingOriginalStackId`
      ]
    },
  },
  methods: {
    async updateKanban(values) {
      const view = this.view
      this.$store.dispatch('view/setItemLoading', { view, value: true })

      try {
        await this.$store.dispatch('view/update', {
          view,
          values,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }

      this.$store.dispatch('view/setItemLoading', { view, value: false })
    },
  },
}
