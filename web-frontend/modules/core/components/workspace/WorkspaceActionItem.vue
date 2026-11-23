<template>
  <li
    v-if="action"
    class="context__menu-item"
    :class="{ 'context__menu-item--with-separator': separator }"
  >
    <NuxtLink
      v-if="action.to"
      :to="action.to"
      prefetch-on="interaction"
      class="context__menu-item-link"
      @click="action.run"
    >
      <i
        class="context__menu-item-icon"
        :class="action.icon"
        aria-hidden="true"
      ></i>
      {{ $t(action.label) }}
      <slot />
    </NuxtLink>
    <button
      v-else
      type="button"
      class="context__menu-item-link workspace-context__action"
      :class="{
        'context__menu-item-link--delete': action.destructive,
        'context__menu-item-link--loading': action.loading,
      }"
      :disabled="action.loading"
      @click="action.run"
    >
      <i
        class="context__menu-item-icon"
        :class="action.icon"
        aria-hidden="true"
      ></i>
      {{ $t(action.label) }}
      <slot />
    </button>
  </li>
</template>

<script setup>
defineProps({
  action: {
    type: Object,
    default: null,
  },
  separator: {
    type: Boolean,
    default: false,
  },
})
</script>
