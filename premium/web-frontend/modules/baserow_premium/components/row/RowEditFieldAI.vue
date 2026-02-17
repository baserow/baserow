<template>
  <div>
    <component
      :is="outputRowEditFieldComponent"
      ref="field"
      v-bind="$props"
      :read-only="generating || readOnly"
      @update="$emit('update', $event)"
    ></component>
    <div v-if="!readOnly" class="margin-top-2">
      <Button
        v-if="isDeactivated && rowIsCreated"
        type="secondary"
        icon="iconoir-lock"
        @click="$refs.clickModal.show()"
      >
        {{ $t('rowEditFieldAI.generate') }}
      </Button>
      <Button
        v-else-if="rowIsCreated"
        type="secondary"
        :loading="generating"
        @click.prevent.stop="generate()"
        >{{ $t('rowEditFieldAI.generate') }}</Button
      >
      <div v-else>{{ $t('rowEditFieldAI.createRowBefore') }}</div>
      <component
        :is="deactivatedClickComponent[0]"
        v-if="isDeactivated"
        ref="clickModal"
        :workspace="workspace"
        name="ai-field"
        v-bind="deactivatedClickComponent[1]"
      ></component>
      <div v-if="generationError" class="margin-top-1">
        <i
          class="iconoir-warning-triangle"
          style="color: var(--color-warning)"
        ></i>
        {{ generationError.message }}
      </div>
    </div>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import fieldAI from '@baserow_premium/mixins/fieldAI'

export default {
  name: 'RowEditFieldAI',
  mixins: [rowEditField, fieldAI],
  emits: ['update'],
  computed: {
    fieldName() {
      return this.$registry.get('field', this.field.type).getName()
    },
    outputRowEditFieldComponent() {
      return this.$registry
        .get('aiFieldOutputType', this.field.ai_output_type)
        .getBaserowFieldType()
        .getRowEditFieldComponent(this.field)
    },
  },
}
</script>
