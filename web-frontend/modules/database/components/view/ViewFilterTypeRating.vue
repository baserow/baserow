<template>
  <div class="filters__value-rating">
    <Rating
      :rating-style="field.style"
      :color="field.color"
      :value="copy"
      :max-value="field.max_value"
      @update="delayedUpdate($event, true)"
    />
  </div>
</template>

<script>
import filterTypeInput from '@baserow/modules/database/mixins/filterTypeInput'
import Rating from '@baserow/modules/database/components/Rating'

export default {
  name: 'ViewFilterTypeRating',
  components: { Rating },
  mixins: [filterTypeInput],
  setup: filterTypeInput.setup,
  created() {
    // Value from server is always a string, we need to parse it.
    this.copy = parseInt(this.filter.value, 10)
  },
}
</script>
