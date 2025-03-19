<template>
  <Rating
    :value="value"
    :max-value="maxValue"
    :custom-color="resolveColor(color, colorVariables)"
    :rating-style="ratingStyle || 'star'"
    read-only
    show-unselected
  />
</template>

<script>
import Rating from '@baserow/modules/database/components/Rating'
import collectionField from '@baserow/modules/builder/mixins/collectionField'

export default {
  name: 'RatingField',
  components: {
    Rating,
  },
  mixins: [collectionField],
  props: {
    value: {
      type: Number,
      required: true,
    },
    maxValue: {
      type: Number,
      required: true,
    },
    color: {
      type: String,
      default: '#fcbb03',
    },
    ratingStyle: {
      type: String,
      default: 'star',
    },
  },
}
</script>
