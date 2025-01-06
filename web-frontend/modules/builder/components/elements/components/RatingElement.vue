<script>
import RatingInputElement from './RatingInputElement'

export default {
  name: 'RatingElement',
  extends: RatingInputElement,
  props: {
    editable: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
