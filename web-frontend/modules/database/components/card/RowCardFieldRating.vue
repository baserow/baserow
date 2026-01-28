<template>
  <component
    :is="$options.components.Rating"
    :read-only="true"
    :rating-style="field.style"
    :color="field.color"
    :value="value"
    :max-value="field.max_value"
    class="card-rating"
  ></component>
</template>

<script>
import Rating from '@baserow/modules/database/components/Rating'

export default {
  height: 18,
  name: 'RowCardFieldRating',
  components: { Rating },
  props: {
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: Number,
      default: 0,
    },
  },
}
</script>
