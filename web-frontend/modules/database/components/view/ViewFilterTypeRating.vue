<template>
  <div class="filters__value-rating">
    <Rating
      :rating-style="field.style"
      :color="field.color"
      :value="values.copy"
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
  created() {
    // Value from server is always a string, we need to parse it.
    this.values.copy = parseInt(this.filter.value, 10)
  },
}
</script>
