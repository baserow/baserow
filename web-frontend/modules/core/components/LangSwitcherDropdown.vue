<template>
  <Dropdown
    ref="dropdown"
    v-model="language"
    class="dropdown--floating-left"
    :show-search="false"
    v-bind="$attrs"
  >
    <DropdownItem
      v-for="locale in $i18n.locales"
      :key="locale.code"
      :name="locale.name"
      :value="locale.code"
    ></DropdownItem>
  </Dropdown>
</template>

<script>
export default {
  name: 'LanguageSwitcherDropdown',
  computed: {
    language: {
      get() {
        return this.$i18n.locale
      },
      set(value) {
        this.$i18n.setLocale(value)
      },
    },
  },
  methods: {
    toggle(...args) {
      return this.$refs.dropdown.toggle(...args)
    },
  },
}
</script>
