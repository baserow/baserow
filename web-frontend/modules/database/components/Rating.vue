<template>
  <div
    :class="[
      customColor ? 'rating' : `rating color--${color}`,
      showUnselected ? 'rating--show-unselected' : '',
      readOnly ? '' : 'editing',
    ]"
    :style="{ '--rating-color': customColor }"
  >
    <i
      v-for="index in readOnly && !showUnselected ? value : maxValue"
      :key="index"
      class="rating__star"
      :class="{
        [`baserow-icon-${ratingStyle}`]: true,
        'rating__star--selected': index <= value,
      }"
      @click="onClick(index)"
    />
  </div>
</template>

<script>
import { RATING_STYLES } from '@baserow/modules/core/enums'

export default {
  name: 'Rating',
  props: {
    readOnly: {
      type: Boolean,
      default: false,
    },
    value: {
      required: true,
      type: Number,
    },
    maxValue: {
      required: true,
      type: Number,
    },
    ratingStyle: {
      default: 'star',
      type: String,
      validator(value) {
        return RATING_STYLES[value] === undefined
      },
    },
    showUnselected: {
      type: Boolean,
      default: false,
    },
    // to use one of predefined colors classes
    color: {
      default: 'dark-orange',
      type: String,
    },
    // to use custom color
    customColor: {
      default: '',
      type: String,
    },
  },
  emits: ['update'],
  methods: {
    onClick(index) {
      if (this.readOnly) {
        return
      }
      this.$emit('update', index === this.value ? 0 : index)
    },
  },
}
</script>
