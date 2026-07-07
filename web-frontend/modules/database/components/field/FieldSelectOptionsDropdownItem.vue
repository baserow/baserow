<template>
  <li
    class="select-options__dropdown-item"
    :class="{
      hidden: !isVisible(query),
      active: isActive(value),
      disabled: disabled,
      hover: isHovering(value),
    }"
  >
    <a
      class="select-options__dropdown-link"
      @click="select(value, disabled)"
      @mousemove="hover(value, disabled)"
    >
      <div v-if="multiple.value">
        <Checkbox
          :disabled="disabled"
          :checked="isActive(value)"
          @click.prevent
        ></Checkbox>
      </div>
      <div
        class="select-options__dropdown-option"
        :class="'background-color--' + color"
      >
        {{ name }}
      </div>
    </a>
  </li>
</template>

<script>
import dropdownItem from '@baserow/modules/core/mixins/dropdownItem'

export default {
  name: 'FieldSelectOptionsDropdownItem',
  mixins: [dropdownItem],
  props: {
    color: {
      type: String,
      required: false,
      default: '',
    },
  },
}
</script>
