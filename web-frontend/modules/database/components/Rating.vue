<template functional>
  <div
    :class="[
      data.staticClass,
      props.customColor ? 'rating' : `rating color--${props.color}`,
      props.showUnselected ? 'rating--show-unselected' : '',
      props.readOnly ? '' : 'editing',
    ]"
    :style="{ '--rating-color': props.customColor }"
  >
    <i
      v-for="index in props.readOnly && !props.showUnselected
        ? props.value
        : props.maxValue"
      :key="index"
      class="rating__star"
      :class="{
        [`baserow-icon-${props.ratingStyle}`]: true,
        'rating__star--selected': index <= props.value,
      }"
      @click="
        !props.readOnly &&
          listeners['update'] &&
          listeners['update'](index === props.value ? 0 : index)
      "
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
      validator: () => true,
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
}
</script>
