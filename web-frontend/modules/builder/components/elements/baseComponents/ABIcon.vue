<template>
  <i
    class="ab-icon"
    :class="{
      'loading-spinner': loading,
      'ab-icon--button': isButton,
      [icon]: true,
    }"
    :title="title"
    @click="$emit('click', $event)"
  />
</template>

<script>
export default {
  name: 'ABIcon',
  props: {
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    isButton: {
      type: Boolean,
      default: false,
    },
    icon: {
      type: String,
      required: true,
    },
    title: {
      type: String,
      default: '',
    },
  },
}
</script>
