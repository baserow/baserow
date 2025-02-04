<script>
import RatingInputElement from './RatingInputElement'

export default {
  name: 'RatingElement',
  extends: RatingInputElement,
  props: {
    readOnly: {
      type: Boolean,
      default: true,
    },
  },
}
</script>
