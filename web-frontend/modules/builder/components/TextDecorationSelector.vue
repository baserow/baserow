<template>
  <div class="text-decoration-selector">
    <SwitchButton
      :value="value[0]"
      :icon="'iconoir-underline'"
      :title="$t('textDecorationSelector.underline')"
      @input="toggle(0)"
    />
    <SwitchButton
      :value="value[1]"
      :icon="'iconoir-strikethrough'"
      :title="$t('textDecorationSelector.stroke')"
      @input="toggle(1)"
    />
    <SwitchButton
      :value="value[2]"
      :icon="'iconoir-text'"
      :title="$t('textDecorationSelector.uppercase')"
      @input="toggle(2)"
    />
    <SwitchButton
      :value="value[3]"
      :icon="'iconoir-italic'"
      :title="$t('textDecorationSelector.italic')"
      @input="toggle(3)"
    />
  </div>
</template>

<script>
export default {
  name: 'TextDecorationSelector',
  props: {
    value: {
      type: Array,
      required: false,
      default: () => [false, false, false, false],
    },
  },
  methods: {
    toggle(index) {
      this.$emit(
        'input',
        this.value.map((v, i) => (i === index ? !v : v))
      )
    },
  },
}
</script>
