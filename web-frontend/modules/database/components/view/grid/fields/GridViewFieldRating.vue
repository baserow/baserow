<template>
  <div ref="cell" class="grid-view__cell active">
    <div class="grid-field-rating">
      <Rating
        :read-only="readOnly"
        :rating-style="field.style"
        :color="field.color"
        :value="value"
        :max-value="field.max_value"
        @update="update"
      />
    </div>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import Rating from '@baserow/modules/database/components/Rating'

export default {
  components: { Rating },
  mixins: [gridField],
  emits: ['update'],
  mounted() {
    window.addEventListener('keyup', this.keyup)
  },
  beforeUnmount() {
    window.removeEventListener('keyup', this.keyup)
  },
  methods: {
    update(newValue) {
      this.$emit('update', newValue, this.value)
    },
    keyup(event) {
      // Allow keyboard modification
      const { key } = event
      let newValue = this.value

      if ('0123456789'.includes(key)) {
        // Transform digit in value
        newValue = parseInt(key, 10)
      } else {
        // +, > to increase -, < to decrease
        switch (key) {
          case '+':
          case '>':
            newValue = this.value + 1
            break
          case '-':
          case '<':
            newValue = this.value - 1
            break
        }
      }
      if (newValue !== this.value) {
        // Clamp value
        if (newValue > this.field.max_value) {
          newValue = this.field.max_value
        }
        if (newValue < 0) {
          newValue = 0
        }
        this.$emit('update', newValue, this.value)
      }
    },
  },
}
</script>
