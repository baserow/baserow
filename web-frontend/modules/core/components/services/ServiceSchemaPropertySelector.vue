<template>
  <div>
    <p v-show="value === null" class="margin-bottom-1">
      <slot name="chooseValueState"></slot>
    </p>
    <Dropdown
      :value="value"
      :size="small ? 'regular' : 'large'"
      :placeholder="placeholder"
      :show-search="true"
      @input="$emit('input', $event)"
    >
      <DropdownItem
        v-for="schemaProp in schemaProperties"
        :key="schemaProp.uniqueId"
        :name="schemaProp.title"
        :value="schemaProp.uniqueId"
      >
      </DropdownItem>
      <template #emptyState>
        <slot name="emptyState">
          {{ $t('serviceSchemaPropertySelector.noProperties') }}
        </slot>
      </template>
    </Dropdown>
  </div>
</template>

<script>
export default {
  name: 'ServiceSchemaPropertySelector',
  props: {
    schema: {
      type: Object,
      required: false,
      default: null,
    },
    value: {
      type: String,
      required: false,
      default: null,
    },
    placeholder: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * The type of the schema property to select.
     * By default, will only display 'array' type properties.
     */
    type: {
      type: String,
      required: false,
      default: 'array',
    },
    small: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    schemaProperties() {
      if (!this.schema) return []
      const schemaProperties =
        this.schema.type === 'array'
          ? this.schema.items.properties
          : this.schema.properties
      return Object.entries(schemaProperties)
        .filter(([_, property]) => property.type === this.type)
        .map(([key, property]) => ({
          uniqueId: key,
          title: property.title,
          type: property.type,
          original_type: property.original_type,
        }))
    },
  },
}
</script>
