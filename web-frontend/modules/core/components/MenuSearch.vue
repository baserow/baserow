<template>
  <div class="menu-search">
    <i class="menu-search__icon iconoir-search" />
    <input
      ref="input"
      :value="modelValue"
      class="menu-search__input"
      type="search"
      :placeholder="placeholder"
      @input="emit('update:modelValue', $event.target.value)"
      @keydown="emit('keydown', $event)"
    />
    <button
      v-if="modelValue"
      type="button"
      class="menu-search__reset"
      :aria-label="$t('dropdown.clearSearch')"
      @click="clear"
    >
      <i class="iconoir-cancel" />
    </button>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'

defineProps({
  modelValue: {
    type: String,
    required: false,
    default: '',
  },
  placeholder: {
    type: String,
    required: false,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'keydown'])

const input = ref(null)

function focus() {
  input.value?.focus()
}

async function clear() {
  emit('update:modelValue', '')
  await nextTick()
  focus()
}

defineExpose({ focus })
</script>
