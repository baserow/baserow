<template>
  <FormGroup
    :label="$t('semanticSearchFieldSetting.label')"
    :small-label="true"
    horizontal-variable
    required
  >
    <template v-if="!hasFeature" #after-label>
      <i class="iconoir-lock"></i>
    </template>
    <div class="control__elements flex justify-content-end">
      <SwitchInput
        v-tooltip="disabledReason"
        :value="isCompatible && values.semantic_search_enabled"
        :small="true"
        :disabled="!!disabledReason"
        class="inline-flex"
        @input="toggle"
      ></SwitchInput>
    </div>
  </FormGroup>
  <div class="control__messages padding-top-0">
    <p
      v-if="error"
      class="control__messages--error field-context__inner-element-width"
    >
      {{ error }}
    </p>
    <p
      v-if="statusMessage"
      class="control__helper-text field-context__inner-element-width"
    >
      {{ statusMessage }}
    </p>
    <p class="control__helper-text field-context__inner-element-width">
      {{ $t('semanticSearchFieldSetting.description') }}
    </p>
    <div v-if="isUpdating" class="semantic-search-field-setting__updating">
      <span class="semantic-search-field-setting__spinner"></span>
      {{ $t('semanticSearchFieldSetting.indexing') }}
    </div>
  </div>
  <PaidFeaturesModal
    ref="paidFeaturesModal"
    :workspace="database.workspace"
    :initial-selected-type="paidFeatureType"
  ></PaidFeaturesModal>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import { SemanticSearchPaidFeature } from '@baserow_enterprise/paidFeatures'

// A ready index needs no explanation, and indexing is shown below the toggle.
const STATUS_MESSAGES = {
  error: 'semanticSearchFieldSetting.statusError',
  paused: 'semanticSearchFieldSetting.statusPaused',
  unavailable: 'semanticSearchFieldSetting.statusUnavailable',
}
const ERROR_MESSAGES = {
  ERROR_SEMANTIC_SEARCH_NOT_AVAILABLE: 'semanticSearchFieldSetting.unavailable',
  ERROR_SEMANTIC_SEARCH_NOT_SUPPORTED:
    'semanticSearchFieldSetting.incompatible',
}

export default {
  name: 'SemanticSearchFieldSetting',
  components: { PaidFeaturesModal },
  mixins: [form],
  props: {
    fieldValues: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
  },
  emits: ['show'],
  data() {
    return {
      allowedValues: ['semantic_search_enabled'],
      values: { semantic_search_enabled: false },
      error: null,
      paidFeatureType: SemanticSearchPaidFeature.getType(),
    }
  },
  computed: {
    hasFeature() {
      return this.$hasFeature(
        EnterpriseFeatures.SEMANTIC_SEARCH,
        this.database.workspace.id
      )
    },
    isAvailable() {
      return !!this.$store.getters['settings/get'].semantic_search?.available
    },
    isCompatible() {
      const type = this.fieldValues.type
      if (!type || !this.$registry.exists('semanticSearchFieldType', type)) {
        return false
      }
      return this.$registry
        .get('semanticSearchFieldType', type)
        .isCompatible(this.fieldValues)
    },
    disabledReason() {
      // Disabling is still possible, so that the vectors can be cleaned up.
      if (!this.isAvailable && !this.defaultValues.semantic_search_enabled) {
        return this.$t('semanticSearchFieldSetting.unavailable')
      }
      if (!this.isCompatible) {
        return this.$t('semanticSearchFieldSetting.incompatible')
      }
      return null
    },
    // The status is of the saved field, so it doesn't apply while toggling.
    isStatusRelevant() {
      return (
        this.values.semantic_search_enabled &&
        this.defaultValues.semantic_search_enabled
      )
    },
    isUpdating() {
      return (
        this.isStatusRelevant &&
        this.defaultValues.semantic_search_status === 'indexing'
      )
    },
    statusMessage() {
      const message = STATUS_MESSAGES[this.defaultValues.semantic_search_status]
      return message && this.isStatusRelevant ? this.$t(message) : null
    },
  },
  methods: {
    toggle(enabled) {
      // Disabling is always possible, also without a license.
      if (enabled && !this.hasFeature) {
        this.$refs.paidFeaturesModal.show()
        return
      }
      this.error = null
      this.values.semantic_search_enabled = enabled
    },
    getFormValues() {
      // Converting to an incompatible type disables semantic search in the backend.
      return this.isCompatible ? { ...this.values } : {}
    },
    handleErrorByForm(error) {
      const message = ERROR_MESSAGES[error.handler?.code]
      if (message) {
        this.error = this.$t(message)
        this.$emit('show')
        return true
      }
      return false
    },
  },
}
</script>
