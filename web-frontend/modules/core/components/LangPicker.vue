<template>
  <div class="lang-picker">
    <a
      ref="dropdownLink"
      class="lang-picker__link"
      @click="$refs.dropdown.toggle($refs.dropdownLink)"
    >
      {{ visibleLanguageName }}
      <i class="iconoir-nav-arrow-down lang-picker__icon"></i>
    </a>
    <LanguageSwitcherDropdown
      ref="dropdown"
      class="lang-picker__dropdown"
      :show-input="false"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import LanguageSwitcherDropdown from '@baserow/modules/core/components/LangSwitcherDropdown'

const { locale, locales } = useI18n()

const visibleLanguageName = computed(() => {
  const currentLocale = locales.value.find((l) => l.code === locale.value)
  return currentLocale?.name || ''
})
</script>
