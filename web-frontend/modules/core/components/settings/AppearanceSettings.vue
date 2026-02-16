<template>
  <div>
    <h2 class="box__title">{{ $t('appearanceSettings.title') }}</h2>
    <p class="margin-bottom-2">{{ $t('appearanceSettings.description') }}</p>
    <div class="appearance-settings__options">
      <label
        v-for="option in themeOptions"
        :key="option.value"
        class="appearance-settings__option"
        :class="{
          'appearance-settings__option--active': preference === option.value,
        }"
      >
        <input
          v-model="preference"
          type="radio"
          name="theme"
          :value="option.value"
          class="appearance-settings__radio"
          @change="setTheme(option.value)"
        />
        <span class="appearance-settings__icon">
          <i :class="option.icon"></i>
        </span>
        <span class="appearance-settings__label">{{ option.label }}</span>
      </label>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      preference: this.$store.getters['uiTheme/getPreference'],
    }
  },
  computed: {
    themeOptions() {
      return [
        {
          value: 'dark',
          label: this.$t('appearanceSettings.dark'),
          icon: 'iconoir-half-moon',
        },
        {
          value: 'light',
          label: this.$t('appearanceSettings.light'),
          icon: 'iconoir-sun-light',
        },
        {
          value: 'system',
          label: this.$t('appearanceSettings.system'),
          icon: 'iconoir-computer',
        },
      ]
    },
  },
  methods: {
    setTheme(value) {
      this.$store.dispatch('uiTheme/setTheme', value)
    },
  },
}
</script>
