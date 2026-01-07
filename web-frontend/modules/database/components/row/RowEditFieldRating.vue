<template>
  <div class="control__elements">
    <div class="field-rating">
      <Rating
        :rating-style="field.style"
        :color="field.color"
        :value="value"
        :max-value="field.max_value"
        :read-only="readOnly"
        @update="update"
      />
    </div>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'

import Rating from '@baserow/modules/database/components/Rating'

export default {
  emits: ['update'],

  components: { Rating },
  mixins: [rowEditField],
  methods: {
    update(newValue) {
      this.$emit('update', newValue, this.value)
    },
  },
}
</script>
