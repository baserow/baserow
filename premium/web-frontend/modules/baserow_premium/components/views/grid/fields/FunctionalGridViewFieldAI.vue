<template functional>
  <div
    v-if="
      (!props.value || $options.methods.isGenerating(parent, props)) &&
      !props.readOnly
    "
    class="grid-view__cell"
  >
    <div class="grid-field-button">
      <Button
        tag="a"
        size="tiny"
        type="secondary"
        :loading="$options.methods.isGenerating(parent, props)"
        :disabled="!$options.methods.isModelAvailable(parent, props)"
        :icon="
          $options.methods.isDeactivatedFunctional(parent, props)
            ? 'iconoir-lock'
            : ''
        "
      >
        <i18n path="functionalGridViewFieldAI.generate" tag="span" />
      </Button>
    </div>
  </div>
  <component
    :is="$options.methods.getFunctionalOutputFieldComponent(parent, props)"
    v-else
    :workspace-id="props.workspaceId"
    :field="props.field"
    :value="props.value"
    :state="props.state"
    :read-only="props.readOnly"
  />
</template>

<script>
import gridFieldAI from '@baserow_premium/mixins/gridFieldAI'
import { AIFieldType } from '@baserow_premium/fieldTypes'

export default {
  name: 'FunctionalGridViewFieldAI',
  mixins: [gridFieldAI],
  methods: {
    isDeactivatedFunctional(parent, props) {
      return parent.$registry
        .get('field', AIFieldType.getType())
        .isDeactivated(props.workspaceId)
    },
    getFunctionalOutputFieldComponent(parent, props) {
      return parent.$registry
        .get('aiFieldOutputType', props.field.ai_output_type)
        .getBaserowFieldType()
        .getFunctionalGridViewFieldComponent(props.field)
    },
  },
}
</script>
