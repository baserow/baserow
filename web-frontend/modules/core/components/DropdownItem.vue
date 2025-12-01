<template>
  <li
    v-if="visible"
    class="select__item select__item--no-options"
    :class="{
      hidden: !isVisible(query),
      visible: isVisible(query),
      active: isActive(value),
      disabled: disabled,
      hover: isHovering(value),
    }"
    role="listitem"
    @click="$emit('click', $event)"
  >
    <a
      class="select__item-link"
      :class="{ 'select__item-link--indented': indented }"
      @click="select(value, disabled)"
      @mousemove="hover(value, disabled)"
    >
      <div class="select__item-name">
        <div v-if="multiple.value">
          <Checkbox :disabled="disabled" :checked="isActive(value)"></Checkbox>
        </div>
        <slot>
          <i
            v-if="icon"
            v-tooltip="iconTooltip"
            class="select__item-icon"
            :class="icon"
          />
          <img v-if="image" class="select__item-image" :src="image" />
          <span
            class="select__item-name-text"
            :class="{ 'select__item-name-text--forced-height': !name }"
            :title="name"
            >{{ name }}</span
          >
        </slot>
      </div>
      <div v-if="description !== null" class="select__item-description">
        {{ description }}
      </div>
    </a>
    <i
      v-if="!multiple.value"
      class="select__item-active-icon iconoir-check"
    ></i>
  </li>
</template>

<script>
import dropdownItem from '@baserow/modules/core/mixins/dropdownItem'

export default {
  name: 'DropdownItem',
  mixins: [dropdownItem],
}
</script>
