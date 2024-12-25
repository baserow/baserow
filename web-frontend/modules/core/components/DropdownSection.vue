<template>
  <div class="dropdown-section">
    <div class="dropdown-section__title">{{ title }}</div>
    <slot></slot>
  </div>
</template>

<script>
export default {
  name: 'DropdownSection',
  props: {
    title: {
      type: String,
      required: true,
    },
  },
}
</script>
