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
      this.localValue = newValue
    },
  },
  methods: {
    defaultEmptyFormula() {
      return {
        enabled: true,
        value: { formula: '""' },
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
