<template>
  <Dropdown
    ref="dropdown"
    v-model="language"
    class="dropdown--floating-left"
    :show-search="false"
    v-bind="$attrs"
  >
    <DropdownItem
      v-for="locale in locales"
      :key="locale.code"
      :name="locale.name"
      :value="locale.code"
    />
  </Dropdown>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const dropdown = ref(null)

const { locale, locales } = useI18n()

const language = computed({
  get: () => locale.value,
  set: (value) => {
    locale.value = value
  },
})

const toggle = (...args) => {
  return dropdown.value?.toggle?.(...args)
}

defineExpose({
  toggle,
})
</script>
