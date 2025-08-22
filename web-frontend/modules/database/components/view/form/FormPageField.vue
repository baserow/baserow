<template>
  <div class="form-view__field-wrapper">
    <div class="form-view__field">
      <div class="form-view__field-inner">
        <div class="form-view__field-name">
          {{ field.name }}
          <span v-if="field.required" class="form-view__field-required">*</span>
        </div>
        <!-- prettier-ignore -->
        <div v-if="field.description" class="form-view__field-description whitespace-pre-wrap">{{ field.description }}</div>
        <component
          :is="selectedFieldComponent.component"
          :key="field.field.id"
          ref="field"
          :workspace-id="0"
          :slug="slug"
          :field="field.field"
          :value="value"
          :read-only="false"
          :required="field.required"
          :touched="field._.touched"
          v-bind="selectedFieldComponent.properties"
          @update="$emit('input', $event)"
          @touched="field._.touched = true"
        />
      </div>
    </div>
  </div>
</template>

<script>
import FieldContext from '@baserow/modules/database/components/field/FieldContext'
import { DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY } from '@baserow/modules/database/constants'

export default {
  name: 'FormPageField',
  components: { FieldContext },
  props: {
    slug: {
      type: String,
      required: true,
    },
    value: {
      required: true,
      validator: () => true,
    },
    field: {
      type: Object,
      required: true,
    },
  },
  computed: {
    selectedFieldComponent() {
      const components = this.$registry
        .get('field', this.field.field.type)
        .getFormViewFieldComponents(this.field.field, this)
      return Object.prototype.hasOwnProperty.call(
        components,
        this.field.field_component
      )
        ? components[this.field.field_component]
        : components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY]
    },
  },
  methods: {
    focus() {
      this.$el.scrollIntoView({ behavior: 'smooth' })
      this.$emit('focussed')
    },
    isValid() {
      return this.$refs.field.isValid()
    },
  },
}
</script>
