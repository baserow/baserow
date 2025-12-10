<template>
  <div v-if="shouldShowGenerateButton" class="grid-view__cell">
    <div class="grid-field-button">
      <Button
        tag="a"
        size="tiny"
        type="secondary"
        :loading="generating"
        :disabled="!modelAvailable"
        :icon="isDeactivatedFunctional ? 'iconoir-lock' : ''"
      >
        <i18n-t keypath="functionalGridViewFieldAI.generate" tag="span" />
      </Button>
    </div>
  </div>
  <component
    :is="functionalOutputFieldComponent"
    v-else
    :workspace-id="workspaceId"
    :field="field"
    :value="value"
    :state="state"
    :read-only="readOnly"
  />
</template>

<script>
import gridFieldAI from '@baserow_premium/mixins/gridFieldAI'
import { AIFieldType } from '@baserow_premium/fieldTypes'

export default {
  name: 'FunctionalGridViewFieldAI',
  mixins: [gridFieldAI],
  props: {
    row: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: null,
      default: null,
    },
    state: {
      type: Object,
      required: true,
    },
    workspaceId: {
      type: [Number, String],
      required: true,
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
    storePrefix: {
      type: String,
      default: '',
    },
  },
  computed: {
    shouldShowGenerateButton() {
      return (!this.value || this.generating) && !this.readOnly
    },
    functionalOutputFieldComponent() {
      return this.$registry
        .get('aiFieldOutputType', this.field.ai_output_type)
        .getBaserowFieldType()
        .getFunctionalGridViewFieldComponent(this.field)
    },
    isDeactivatedFunctional() {
      return this.$registry
        .get('field', AIFieldType.getType())
        .isDeactivated(this.workspaceId)
    },
  },
}
</script>
