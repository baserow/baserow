<template>
  <div class="rating-field">
    <div class="rating" :style="{ '--rating-color': color }">
      <Rating
        :value="value"
        :max-value="maxValue"
        :color="'custom'"
        :rating-style="iconStyle || 'star'"
        :read-only="true"
        :show-unselected-in-read-only="true"
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
    iconStyle: {
      type: String,
      default: 'star',
    },
  },
}
</script>

<style lang="scss">
@import '@baserow/modules/core/assets/scss/colors';
@import '@baserow/modules/core/assets/scss/placeholders';
@import '@baserow/modules/core/assets/scss/mixins/helpers';
@import '@baserow/modules/core/assets/scss/components/rating';
.rating-field {
  .rating {
    .rating__star.rating__star {
      color: var(--rating-color) !important;
      opacity: 0.3;

      &.rating__star--selected {
        opacity: 1;
      }
    }
  }
}
</style>
