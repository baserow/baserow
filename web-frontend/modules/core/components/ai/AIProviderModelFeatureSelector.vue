<template>
  <fieldset class="ai-provider-feature-selector">
    <legend class="ai-provider-feature-selector__legend">
      {{ $t('aiProviderAdmin.availableFor') }}
    </legend>
    <p class="ai-provider-feature-selector__description">
      {{ $t('aiProviderAdmin.availableForDescription') }}
    </p>
    <div class="ai-provider-feature-selector__options">
      <Checkbox
        v-for="feature in features"
        :key="feature.getType()"
        :model-value="modelValue.includes(feature.getType())"
        @update:model-value="setFeature(feature.getType(), $event)"
      >
        {{ feature.getName() }}
      </Checkbox>
    </div>
  </fieldset>
</template>

<script>
export default {
  name: 'AIProviderModelFeatureSelector',
  props: {
    modelValue: { type: Array, required: true },
  },
  emits: ['update:modelValue'],
  computed: {
    features() {
      return this.$registry.getOrderedList('aiProviderModelFeature')
    },
  },
  methods: {
    setFeature(type, enabled) {
      const selected = new Set(this.modelValue)
      if (enabled) selected.add(type)
      else selected.delete(type)
      this.$emit('update:modelValue', [...selected])
    },
  },
}
</script>
