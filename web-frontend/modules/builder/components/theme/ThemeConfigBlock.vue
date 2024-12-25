<template>
  <div
    class="theme-config-block"
    :class="{
      'theme-config-block--no-preview': !preview,
    }"
  >
    <component
      :is="themeConfigBlockType.component"
      ref="themeConfigBlockForm"
      :preview="preview"
      :theme="theme"
      :extra-args="extraArgs"
      :default-values="defaultValues"
      @values-changed="$emit('values-changed', $event)"
    />
  </div>
</template>

<script>
export default {
  name: 'ThemeConfigBlock',
  props: {
    defaultValues: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    theme: { type: Object, required: false, default: null },
    themeConfigBlockType: {
      type: Object,
      required: true,
    },
    extraArgs: {
      type: Object,
      required: false,
      default: null,
    },
    preview: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  methods: {
    reset() {
      this.$refs.themeConfigBlockForm.reset()
    },
    isFormValid() {
      return this.$refs.themeConfigBlockForm.isFormValid()
    },
  },
}
</script>
