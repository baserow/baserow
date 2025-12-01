<template>
  <div class="device-selector" data-highlight="builder-devices">
    <div
      v-for="(deviceType, index) in deviceTypes"
      :key="index"
      class="device-selector__item"
      :class="`device-selector__item--${direction}`"
    >
      <RadioButton
        :key="deviceType.getType()"
        :value="deviceType.getType()"
        :icon="deviceType.iconClass"
        :model-value="deviceTypeSelected"
        class="device-selector__button"
        @click.native="$emit('selected', deviceType.getType())"
      ></RadioButton>
      <slot name="deviceTypeControl" :device-type="deviceType"></slot>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DeviceSelector',
  props: {
    deviceTypeSelected: {
      type: String,
      required: true,
    },
    direction: {
      type: String,
      required: false,
      default: 'column',
    },
  },
  computed: {
    deviceTypes() {
      return Object.values(this.$registry.getOrderedList('device'))
    },
  },
}
</script>
