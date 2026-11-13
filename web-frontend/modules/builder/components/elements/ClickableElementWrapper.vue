<template>
  <div
    v-bind="clickableElementAttributes"
    :class="{ 'element--clickable': isClickable }"
    @click="onElementClick"
    @keydown="onElementKeydown"
    @keyup="onElementKeyup"
  >
    <slot />
  </div>
</template>

<script>
import clickableElement from '@baserow/modules/builder/mixins/clickableElement'

export default {
  name: 'ClickableElementWrapper',
  mixins: [clickableElement],
}
</script>
