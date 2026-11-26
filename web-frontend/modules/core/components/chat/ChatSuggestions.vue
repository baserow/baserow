<template>
  <div class="chat-suggestions">
    <button
      v-for="(suggestion, index) in suggestions"
      :key="index"
      type="button"
      class="chat-suggestions__item"
      @click="$emit('pick', suggestion)"
    >
      <i
        class="chat-suggestions__icon"
        :class="ICONS[index % ICONS.length]"
        aria-hidden="true"
      ></i>
      <span class="chat-suggestions__text">{{ suggestion }}</span>
    </button>
  </div>
</template>

<script setup>
/** Messages a new conversation offers to start with. */
defineProps({ suggestions: { type: Array, required: true } })
defineEmits(['pick'])

const ICONS = [
  'iconoir-chat-lines',
  'iconoir-light-bulb',
  'iconoir-search',
  'iconoir-sparks',
]
</script>
