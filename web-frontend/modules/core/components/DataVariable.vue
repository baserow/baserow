<template>
  <ul
    class="data-variable"
    :class="{
      'data-variable--disabled': disabled,
      'data-variable--active': active,
      'data-variable--error': error,
    }"
  >
    <template v-for="(variable, index) in variables">
      <li :key="variable.id" class="data-variable__item">
        {{ variable.label }}
      </li>
      <li v-if="index < variables.length - 1" :key="variable.id * 2">
        <i class="data-variable__item-separator iconoir-nav-arrow-right"></i>
      </li>
    </template>

    <li
      v-if="removeIcon"
      class="data-variable__remove-icon iconoir-cancel"
      @click="$emit('remove')"
    ></li>
  </ul>
</template>

<script>
export default {
  name: 'DataVariable',
  props: {
    variables: {
      type: Array,
      required: true,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    active: {
      type: Boolean,
      default: false,
    },
    error: {
      type: Boolean,
      default: false,
    },
    removeIcon: {
      type: Boolean,
      default: false,
    },
  },
  mounted() {
    console.log(this.variables)
  },
}
</script>
