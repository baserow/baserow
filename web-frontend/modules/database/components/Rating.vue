<template functional>
  <div
    :class="[
      data.staticClass,
      props.customColor ? 'custom-rating' : `rating color--${props.color}`,
      props.readOnly ? '' : 'editing',
    ]"
    :style="{ '--rating-color': props.customColor }"
  >
    <i
      v-for="index in props.readOnly && !props.showMaxValueInReadOnly
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
    showMaxValueInReadOnly: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
