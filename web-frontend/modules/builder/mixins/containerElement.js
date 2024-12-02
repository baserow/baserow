import element from '@baserow/modules/builder/mixins/element'
import { mapGetters } from 'vuex'
import { DIRECTIONS } from '@baserow/modules/builder/enums'

export default {
  mixins: [element],
  computed: {
    ...mapGetters({
      elementSelected: 'element/getSelected',
    }),
    DIRECTIONS: () => DIRECTIONS,
    children() {
      return this.$store.getters['element/getChildren'](
        this.elementPage,
        this.element
      )
    },
    elementSelectedId() {
      return this.elementSelected?.id
    },
  },
}
