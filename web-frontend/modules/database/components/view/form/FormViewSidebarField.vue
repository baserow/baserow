<template>
  <div
    v-tooltip="!compatible ? 'Field is incompatible with form view' : false"
    class="form-view__sidebar-fields-item-wrapper"
  >
    <a
      class="form-view__sidebar-fields-item"
      :class="{
        'form-view__sidebar-fields-item--disabled': readOnly,
        'form-view__sidebar-fields-item--incompatible': !compatible,
      }"
      @click="
        !readOnly &&
          compatible &&
          $emit('updated-field-options', { enabled: true })
      "
    >
      <i
        class="form-view__sidebar-fields-icon"
        :class="field._.type.iconClass"
      ></i>
      <div class="form-view__sidebar-fields-name">
        {{ field.name }}
      </div>
      <i class="form-view__sidebar-fields-hover-arrow iconoir-arrow-right"></i>
    </a>
  </div>
</template>

<script>
export default {
  name: 'FormViewSidebarField',
  props: {
    field: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    compatible() {
      const fieldType = this.$registry.get('field', this.field.type)
      return (
        Object.keys(fieldType.getFormViewFieldComponents(this.field, this))
          .length > 0 && !fieldType.isReadOnlyField(this.field)
      )
    },
  },
}
</script>
