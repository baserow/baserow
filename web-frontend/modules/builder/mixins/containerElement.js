import element from '@baserow/modules/builder/mixins/element'
import { DIRECTIONS } from '@baserow/modules/builder/enums'

export default {
  mixins: [element],
  computed: {
    DIRECTIONS: () => DIRECTIONS,
    children() {
      return this.$store.getters['element/getChildren'](
        this.elementPage,
        this.element
      )
    },
  },
}
