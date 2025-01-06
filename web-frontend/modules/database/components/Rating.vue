<template functional>
  <div
    class="rating"
    :class="[
      data.staticClass,
      `color--${props.color}`,
      props.readOnly ? '' : 'editing',
    ]"
  >
    <i
      v-for="index in props.readOnly && !props.showUnselectedInReadOnly ? props.value : props.maxValue"
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
      required: true,
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
    color: {
      default: 'dark-orange',
      type: String,
    },
    showUnselectedInReadOnly: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
