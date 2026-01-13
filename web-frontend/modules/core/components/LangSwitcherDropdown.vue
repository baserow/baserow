<template>
  <Dropdown
    ref="dropdown"
    v-model="language"
    class="dropdown--floating-left"
    :show-search="false"
    v-bind="$attrs"
  >
    <DropdownItem
      v-for="loc in locales"
      :key="loc.code"
      :name="loc.name"
      :value="loc.code"
    />
  </Dropdown>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const dropdown = ref(null)

const { locale, locales, setLocale } = useI18n()

const language = computed({
  get: () => locale.value,
  set: async (value) => {
    await setLocale(value)
  },
})

const toggle = (...args) => {
  return dropdown.value?.toggle?.(...args)
}

defineExpose({
  toggle,
})
</script>
