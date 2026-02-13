<template>
  <div class="grid-view__cell">
    <div class="grid-field-rating">
      <component
        :is="$options.components.Rating"
        :read-only="true"
        :rating-style="field.style"
        :color="field.color"
        :value="value"
        :max-value="field.max_value"
      ></component>
    </div>
  </div>
</template>

<script>
import Rating from '@baserow/modules/database/components/Rating'

export default {
  name: 'FunctionalGridViewFieldRating',
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
