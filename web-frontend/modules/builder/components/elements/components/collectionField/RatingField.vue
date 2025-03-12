<template>
  <div class="rating-field">
    <div>
      <Rating
        :value="value"
        :max-value="maxValue"
        :color="'custom'"
        :custom-color="color"
        :rating-style="ratingStyle || 'star'"
        :read-only="true"
        :show-max-value-in-read-only="true"
      />
    </div>
  </div>
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
      default: 5,
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
