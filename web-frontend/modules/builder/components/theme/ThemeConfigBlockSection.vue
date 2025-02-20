<template>
  <Expandable default-expanded>
    <template #header="{ toggle, expanded }">
      <a v-if="title" class="theme-config-block__title" @click="toggle">
        {{ title }}
        <i
          class="theme-config-block__title-icon"
          :class="{
            'iconoir-nav-arrow-down': expanded,
            'iconoir-nav-arrow-right': !expanded,
          }"
        />
      </a>
    </template>
    <template #default>
      <div class="theme-config-block-section">
        <div class="theme-config-block-section__properties">
          <slot></slot>
        </div>
        <div v-if="hasSlotPreview" class="theme-config-block-section__preview">
          <slot name="preview"></slot>
        </div>
      </div>
    </template>
  </Expandable>
</template>

<script>
export default {
  name: 'ThemeConfigBlockSection',
  props: {
    title: {
      type: String,
      required: false,
      default: null,
    },
  },
  computed: {
    hasSlotPreview() {
      return !!this.$slots.preview
    },
  },
}
</script>
