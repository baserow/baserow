<template>
  <div>
    <div
      v-if="(!value || generating) && !readOnly"
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
      :workspace-id="workspaceId"
      :field="field"
      :value="value"
      :selected="selected"
      :store-prefix="storePrefix"
      :read-only="readOnly || generating"
      :row="row"
      :all-fields-in-table="allFieldsInTable"
      v-bind="$attrs"
      @editing-changed="(e) => (editing = e)"
      @update="(...args) => $emit('update', ...args)"
      @select-below="(...args) => $emit('selectBelow', ...args)"
      @add-row-after="(...args) => $emit('add-row-after', ...args)"
    >
      <template v-if="!readOnly && editing" #default>
        <div style="background-color: #fff; padding: 8px">
          <ButtonText
            v-if="!isDeactivated"
            icon="iconoir-magic-wand"
            :disabled="!modelAvailable || generating"
            :loading="generating"
            @mousedown.prevent.stop="generate()"
          >
            {{ $t('gridViewFieldAI.regenerate') }}
          </ButtonText>
          <ButtonText
            v-else
            icon="iconoir-lock"
            @mousedown.prevent.stop="$refs.clickModal.show()"
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
import gridFieldAI from '@baserow_premium/mixins/gridFieldAI'

export default {
  name: 'GridViewFieldAI',
  mixins: [gridField, gridFieldAI],
  emits: ['update', 'selectBelow', 'add-row-after'],
  data() {
    return {
      editing: false,
      keydownEventListener: null,
    }
  },
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
    select() {
      this.keydownEventListener = (event) => {
        if (event.key === 'Enter') {
          // When the field is selected but doesn't have any generated value yet,
          // we want to trigger AI generation
          if (!this.value && !this.readOnly) {
            this.generate()
          }
        }
      }
      document.body.addEventListener('keydown', this.keydownEventListener)
    },
    beforeUnSelect() {
      document.body.removeEventListener('keydown', this.keydownEventListener)
    },
    canKeyDown() {
      if (this.$refs.cell && typeof this.$refs.cell.canKeyDown === 'function') {
        return this.$refs.cell.canKeyDown()
      }
      return true
    },
    canKeyboardShortcut() {
      // Since this component is based on gridField mixin
      // we need to make sure that keyboard shortcuts are
      // restricted only to non-editing mode
      if (
        this.$refs.cell &&
        typeof this.$refs.cell.canKeyboardShortcut === 'function'
      ) {
        return this.$refs.cell.canKeyboardShortcut()
      }
      return true
    },
    canUnselectByClickingOutside(event) {
      if (this.isDeactivated && this.workspace) {
        return !isElement(this.$refs.clickModal.$el, event.target)
      }
      return true
    },
    canSelectNext(event) {
      if (
        this.$refs.cell &&
        typeof this.$refs.cell.canSelectNext === 'function'
      ) {
        return this.$refs.cell.canSelectNext(event)
      }
      return true
    },
  },
}
</script>
