<template>
  <div class="decorator-item">
    <img class="decorator-item__image" :src="decoratorType.getImage()" />
    <div class="decorator-item__content">
      <div class="decorator-item__title">
        {{ decoratorType.getName() }}
        <div v-if="deactivated" class="deactivated-label">
          <i class="iconoir-lock"></i>
        </div>
      </div>
      <div class="decorator-item__description">
        {{ decoratorType.getDescription() }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ViewDecoratorItem',
  props: {
    decoratorType: {
      type: Object,
      required: true,
    },
    deactivated: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
