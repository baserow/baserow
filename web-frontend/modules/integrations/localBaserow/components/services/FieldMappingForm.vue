<template>
  <div v-if="mapping?.enabled">
    <FormGroup
      small-label
      :label="field.name"
      :help-icon-tooltip="field.description"
      required
      class="margin-bottom-2"
    >
      <InViewport>
        <InjectedFormulaInput
          :key="`${field.id} ${mapping.enabled}`"
          v-model="fieldValue"
          :disabled="!mapping.enabled"
          :placeholder="placeholderForType"
          @blur="flushPendingValue"
        />
        <template #placeholder>
          <div class="field-mapping-form__placeholder" />
        </template>
      </InViewport>
      <template #after-input>
        <div :ref="`editFieldMappingOpener`">
          <ButtonIcon
            type="secondary"
            icon="iconoir-more-vert"
            @click="openContext()"
          />
        </div>
        <FieldMappingContext
          :ref="`fieldMappingContext`"
          :field-mapping="mapping"
          @edit="$emit('update', $event)"
        />
      </template>
    </FormGroup>
  </div>
  <div v-else>
    <FormGroup small-label :label="field.name" required class="margin-bottom-2">
      <Button type="secondary" @click="$emit('update', defaultEmptyFormula())">
        {{ $t('fieldMappingContext.enableField') }}
      </Button>
    </FormGroup>
  </div>
</template>

<script>
import FieldMappingContext from '@baserow/modules/integrations/localBaserow/components/services/FieldMappingContext'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import InViewport from '@baserow/modules/core/components/InViewport'

export default {
  name: 'FieldMappingForm',
  components: { FieldMappingContext, InjectedFormulaInput, InViewport },
  inject: ['workspace'],
  props: {
    field: {
      type: Object,
      required: true,
    },
    mapping: {
      type: Object,
      required: false,
      default: undefined,
    },
  },
  emits: ['update'],
  data() {
    return {
      localValue: this.mapping?.value,
      debounceTimeout: null,
    }
  },
  computed: {
    fieldType() {
      return this.$registry.get('field', this.field.type)
    },
    fieldValue: {
      get() {
        return this.localValue
      },
      set(value) {
        this.localValue = value

        // Debouncing value update as it produces performance issues when they are
        // a lot of fields
        clearTimeout(this.debounceTimeout)
        this.debounceTimeout = setTimeout(() => {
          this.debounceTimeout = null
          this.$emit('update', { value })
        }, 500)
      },
    },
    placeholderForType() {
      const expectedType = this.fieldType.getDocsDataType(this.field)
      const capitalizedType =
        expectedType.charAt(0).toUpperCase() + expectedType.slice(1)
      return this.$t(
        `localBaserowUpsertRowServiceForm.fieldMappingPlaceholder${capitalizedType}`
      )
    },
  },
  watch: {
    'mapping.value'(newValue) {
      // Editing/enabling another field makes the parent re-emit the whole
      // mappings array, which re-renders this field with its last *committed*
      // value. If we still have an uncommitted, debounced edit, that would drop
      // the user's input (it's never emitted, so it can't be undone/redone - the
      // set-value action simply never happens). This is easy to hit at a normal
      // pace: type a value, then click to enable the next field within ~500ms.
      // So commit the pending value now instead of losing it. A genuine external
      // change (undo/redo) never coincides with a pending debounce.
      if (this.debounceTimeout) {
        clearTimeout(this.debounceTimeout)
        this.debounceTimeout = null
        this.$emit('update', { value: this.localValue })
        return
      }
      this.localValue = newValue
    },
  },
  beforeUnmount() {
    clearTimeout(this.debounceTimeout)
  },
  methods: {
    /**
     * Applies a debounced edit straight away, so a save triggered by leaving
     * this field sees it.
     */
    flushPendingValue() {
      if (this.debounceTimeout === null) {
        return
      }
      clearTimeout(this.debounceTimeout)
      this.debounceTimeout = null
      this.$emit('update', { value: this.localValue })
    },
    defaultEmptyFormula() {
      // Use the canonical empty formula (''), not the empty-string literal ('""').
      // The formula editor can't represent '""' faithfully - it renders empty and
      // emits '' on its first update, which registers a spurious field-value change.
      // During undo/redo that extra action discards the redo stack ("No more actions
      // to redo"). The field ends up as '' regardless, so this changes no behaviour.
      return {
        enabled: true,
        value: { formula: '' },
      }
    },
    openContext() {
      this.$refs.fieldMappingContext.toggle(
        this.$refs.editFieldMappingOpener,
        'bottom',
        'left',
        4
      )
    },
  },
}
</script>
