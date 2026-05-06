<template>
  <div
    class="grid-view__group-header"
    :class="{ 'grid-view__group-header--collapsed': collapsed }"
    :style="{
      transform: `translateX(-${leftOffset}px)`,
      width: width + 'px',
    }"
  >
    <a
      class="grid-view__group-header-toggle"
      :style="{ width: toggleWidth + 'px' }"
      @click.prevent="$emit('toggle-collapse')"
    >
      <i
        class="iconoir-nav-arrow-right grid-view__group-header-toggle-icon"
        :class="{ 'grid-view__group-header-toggle-icon--expanded': !collapsed }"
      />
    </a>
    <div
      class="grid-view__group-header-label"
      :style="{ paddingLeft: depth * 16 + 'px' }"
    >
      <span class="grid-view__group-header-field-name">
        {{ field.name }}
      </span>
      <div class="grid-view__group-header-value-row">
        <component
          :is="groupByComponent"
          v-if="groupByComponent && !empty"
          class="grid-view__group-header-value"
          :field="field"
          :value="displayValue"
        />
        <span
          v-else
          class="grid-view__group-header-value grid-view__group-header-value--empty"
        >
          (Empty)
        </span>
        <span class="grid-view__group-header-count">
          {{ count }}
        </span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GridViewGroupHeader',
  props: {
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: [String, Number, Boolean, Object, Array],
      required: false,
      default: null,
    },
    count: {
      type: Number,
      required: true,
    },
    depth: {
      type: Number,
      required: true,
    },
    collapsed: {
      type: Boolean,
      required: true,
    },
    leftOffset: {
      type: Number,
      required: false,
      default: 0,
    },
    rowDetailsWidth: {
      type: Number,
      required: false,
      default: 0,
    },
    width: {
      type: Number,
      required: true,
    },
  },
  emits: ['toggle-collapse'],
  computed: {
    groupByComponent() {
      if (!this.field?.type) {
        return null
      }

      const fieldType = this.$registry.get('field', this.field.type)
      return fieldType.getGroupByComponent(this.field)
    },
    displayValue() {
      if (!this.field?.type) {
        return this.value
      }
      if (this.value === null || this.value === undefined) {
        return null
      }

      const fieldType = this.$registry.get('field', this.field.type)
      const value = fieldType.getRowValueFromGroupValue(this.field, this.value)

      if (Array.isArray(value)) {
        return value.map((item) => this.enrichSelectOptionValue(item))
      }

      return this.enrichSelectOptionValue(value)
    },
    empty() {
      return (
        this.displayValue === null ||
        this.displayValue === '' ||
        (Array.isArray(this.displayValue) && this.displayValue.length === 0)
      )
    },
    toggleWidth() {
      return this.rowDetailsWidth > 0 ? this.rowDetailsWidth : 32
    },
  },
  methods: {
    enrichSelectOptionValue(value) {
      if (
        !value ||
        typeof value !== 'object' ||
        value.value !== undefined ||
        !Array.isArray(this.field?.select_options)
      ) {
        return value
      }

      return (
        this.field.select_options.find((option) => option.id === value.id) ||
        value
      )
    },
  },
}
</script>
