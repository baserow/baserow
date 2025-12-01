<template>
  <div>
    <div
      v-if="(!value || (!opened && generating)) && !readOnly"
      ref="cell"
      class="grid-view__cell active"
    >
      <div class="grid-field-button">
        <Button
          type="secondary"
          size="tiny"
          :disabled="!modelAvailable || generating"
          :loading="generating"
          :icon="isDeactivated ? 'iconoir-lock' : ''"
          @click="generate()"
        >
          {{ $t('gridViewFieldAI.generate') }}
        </Button>
      </div>
    </div>
    <component
      :is="outputGridViewFieldComponent"
      v-else
      ref="cell"
      :read-only="readOnly || generating"
      v-bind="$props"
      v-on="$listeners"
    >
      <template v-if="!readOnly && editing" #default="{ editing }">
        <div style="background-color: #fff; padding: 8px">
          <ButtonText
            v-if="!isDeactivated"
            icon="iconoir-magic-wand"
            :disabled="!modelAvailable || generating"
            :loading="generating"
            @click.prevent.stop="generate()"
          >
            {{ $t('gridViewFieldAI.regenerate') }}
          </ButtonText>
          <ButtonText
            v-else
            icon="iconoir-lock"
            @click.prevent.stop="$refs.clickModal.show()"
          >
            {{ $t('gridViewFieldAI.regenerate') }}
          </ButtonText>
        </div>
      </template>
    </component>
    <component
      :is="deactivatedClickComponent[0]"
      v-if="isDeactivated && workspace"
      ref="clickModal"
      v-bind="deactivatedClickComponent[1]"
      name="ai-field"
      :workspace="workspace"
    ></component>
  </div>
</template>

<script>
import { isElement } from '@baserow/modules/core/utils/dom'
import gridField from '@baserow/modules/database/mixins/gridField'
import gridFieldInput from '@baserow/modules/database/mixins/gridFieldInput'
import gridFieldAI from '@baserow_premium/mixins/gridFieldAI'

export default {
  name: 'GridViewFieldAI',
  mixins: [gridField, gridFieldInput, gridFieldAI],
  computed: {
    fieldName() {
      return this.$registry.get('field', this.field.type).getName()
    },
    outputGridViewFieldComponent() {
      return this.$registry
        .get('aiFieldOutputType', this.field.ai_output_type)
        .getBaserowFieldType()
        .getGridViewFieldComponent(this.field)
    },
  },
  watch: {
    value(newValue) {
      const outputType = this.$registry.get(
        'aiFieldOutputType',
        this.field.ai_output_type
      )
      this.$nextTick(() => {
        if (this.$refs.cell) {
          outputType.updateValue(this.$refs.cell, newValue)
        }
      })
    },
  },
  methods: {
    save() {
      this.opened = false
      this.editing = false
      this.afterSave()
    },
    canSaveByPressingEnter(event) {
      return this.$refs.cell.canSaveByPressingEnter(event)
    },
    canUnselectByClickingOutside(event) {
      if (this.isDeactivated && this.workspace) {
        return !isElement(this.$refs.clickModal.$el, event.target)
      }
      return true
    },
  },
}
</script>
