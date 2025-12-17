<template>
  <div class="custom-style-button__wrapper" :class="`custom-style--${variant}`">
    <ButtonText
      v-if="variant === 'float'"
      v-tooltip="$t('customStyle.configureThemeOverrides')"
      class="custom-style__button"
      icon="baserow-icon-settings"
      tooltip-position="bottom-left"
      @click="openPanel()"
    />
    <ButtonIcon
      v-else
      v-tooltip="$t('customStyle.configureThemeOverrides')"
      class="custom-style__button"
      icon="baserow-icon-settings"
      tooltip-position="bottom-left"
      @click="openPanel()"
    />
  </div>
</template>

<script>
export default {
  name: 'CustomStyle',
  inject: ['openCustomStyleForm'],
  props: {
    value: {
      type: Object,
      required: false,
      default: () => undefined,
    },
    variant: {
      required: false,
      type: String,
      default: 'float',
      validator: function (value) {
        return ['float', 'normal'].includes(value)
      },
    },
    theme: { type: Object, required: true },
    configBlockTypes: {
      type: Array,
      required: true,
    },
    styleKey: { type: String, required: true },
    extraArgs: {
      type: Object,
      required: false,
      default: () => null,
    },
    onStylesChanged: {
      type: Function,
      required: false,
      default: null,
    },
  },
  methods: {
    /**
     * When the button is clicked, use the injected function which
     * opens the custom styles form, and set the styles context.
     */
    openPanel() {
      this.openCustomStyleForm({
        theme: this.theme,
        styleKey: this.styleKey,
        extraArgs: this.extraArgs,
        onStylesChanged: this.onStylesChanged,
        configBlockTypes: this.configBlockTypes,
        defaultStyleValues: this.value?.[this.styleKey],
      })
    },
  },
}
</script>
