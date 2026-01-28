<template>
  <li
    class="ab-dropdownitem__item ab-dropdownitem__item--no-options"
    :class="{
      hidden: !isVisible(query),
      active: isActive(value),
      disabled: disabled,
      hover: isHovering(value),
    }"
    @click="$emit('click', $event)"
  >
    <a
      class="ab-dropdownitem__item-link"
      @click="select(value, disabled)"
      @mousemove="hover(value, disabled)"
    >
      <div class="ab-dropdownitem__item-name">
        <div v-if="multiple.value">
          <Checkbox :disabled="disabled" :checked="isActive(value)"></Checkbox>
        </div>
        <slot>
          <span class="ab-dropdownitem__item-name-text" :title="name">{{
            name
          }}</span>
        </slot>
      </div>
      <div
        v-if="description !== null"
        class="ab-dropdownitem__item-description"
      >
        {{ description }}
      </div>
    </a>
    <i
      v-if="!multiple.value"
      class="ab-dropdownitem__item-active-icon iconoir-check"
    ></i>
  </li>
</template>

<script>
import dropdownItem from '@baserow/modules/core/mixins/dropdownItem'

export default {
  name: 'ABDropdownItem',
  mixins: [dropdownItem],
  emits: ['click'],
}
</script>
