<template>
  <div
    class="item-card"
    :class="{ 'item-card--with-actions': !!$slots.actions }"
    role="link"
    tabindex="0"
    :title="title"
    @click="$emit('click')"
    @keydown.enter="selectWithKeyboard($event)"
    @keydown.space="selectWithKeyboard($event)"
  >
    <slot name="icon">
      <ItemIcon :icon="icon" :color="iconColor" :loading="loading"></ItemIcon>
    </slot>

    <div class="item-card__details">
      <div class="item-card__name">
        <slot name="name">{{ name }}</slot>
      </div>
      <div class="item-card__meta">
        <slot name="meta"></slot>
      </div>
    </div>

    <slot name="actions"></slot>
  </div>
</template>

<script>
import ItemIcon from '@baserow/modules/core/components/ItemIcon'

/**
 * Presentational card of the listing pages. It only knows how to look and how to
 * be activated, the owner decides what a click means.
 */
export default {
  name: 'ItemCard',
  components: { ItemIcon },
  props: {
    name: {
      type: String,
      required: false,
      default: '',
    },
    icon: {
      type: String,
      required: false,
      default: '',
    },
    iconColor: {
      type: String,
      required: false,
      default: null,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    title: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['click'],
  methods: {
    selectWithKeyboard(event) {
      // Only when the card itself is focused, so typing in an inline rename or
      // pressing enter on a button in the actions slot keeps its own behaviour.
      if (event.target !== event.currentTarget) {
        return
      }
      event.preventDefault()
      this.$emit('click')
    },
  },
}
</script>
