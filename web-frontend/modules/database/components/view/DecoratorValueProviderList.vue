<template>
  <div
    class="value-provider-list"
    :class="{
      [`value-provider-list--${direction}`]: true,
    }"
  >
    <div
      v-for="valueProviderType in availableValueProviderTypes"
      :key="valueProviderType.getType()"
      class="value-provider-list__item"
      :class="{
        active: valueProviderType.getType() === decoration.value_provider_type,
      }"
      @click="$emit('select', valueProviderType.getType())"
    >
      <DecoratorValueProviderItem :value-provider-type="valueProviderType" />
      <i
        v-if="valueProviderType.getType() === decoration.value_provider_type"
        class="value-provider-list__item-active-icon iconoir-check-circle"
      ></i>
    </div>
  </div>
</template>

<script>
import DecoratorValueProviderItem from '@baserow/modules/database/components/view/DecoratorValueProviderItem'

export default {
  name: 'DecoratorValueProviderList',
  components: { DecoratorValueProviderItem },
  props: {
    decoration: {
      type: Object,
      required: true,
    },
    direction: {
      type: String,
      required: false,
      default: 'column',
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    availableValueProviderTypes() {
      const decorationType = this.$registry.get(
        'viewDecorator',
        this.decoration.type
      )
      return this.$registry
        .getOrderedList('decoratorValueProvider')
        .filter((valueProviderType) =>
          valueProviderType.isCompatible(decorationType)
        )
    },
  },
}
</script>
