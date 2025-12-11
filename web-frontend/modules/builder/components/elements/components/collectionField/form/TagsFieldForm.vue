<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('tagsFieldForm.fieldValuesLabel')"
      class="margin-bottom-2"
      horizontal
      required
    >
      <InjectedFormulaInput
        v-model="values.values"
        :placeholder="$t('tagsFieldForm.fieldValuesPlaceholder')"
      />
      <template #after-input>
        <CustomStyleButton
          v-model="values.styles"
          style-key="cell"
          :config-block-types="['table', 'typography']"
          :theme="baseTheme"
          :on-styles-changed="onFieldStylesChanged"
          :extra-args="{ onlyCell: true, onlyBody: true, noAlignment: true }"
          variant="normal"
        />
      </template>
    </FormGroup>

    <div>
      <FormGroup
        v-if="values.colors_is_formula"
        small-label
        :label="$t('tagsFieldForm.fieldColorsLabel')"
        horizontal
        class="margin-bottom-2"
        required
      >
        <InjectedFormulaInput
          v-model="values.colors"
          :placeholder="$t('tagsFieldForm.fieldColorsPlaceholder')"
        />
        <template #after-input>
          <ButtonIcon
            icon="iconoir-color-picker"
            type="secondary"
            @click="setColorsToPicker"
          />
        </template>
      </FormGroup>
      <FormGroup
        v-else
        horizontal
        small-label
        :label="$t('tagsFieldForm.fieldColorsLabel')"
        class="margin-bottom-2"
      >
        <ColorInput
          v-model="rawFormula"
          :color-variables="colorVariables"
          small
        />
        <template #after-input>
          <ButtonIcon
            icon="iconoir-sigma-function"
            type="secondary"
            @click="setColorsToFormula"
          />
        </template>
      </FormGroup>
    </div>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'

export default {
  name: 'TagsField',
  components: { InjectedFormulaInput, CustomStyleButton },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['values', 'colors', 'colors_is_formula', 'styles'],
      values: {
        values: {},
        colors: {
          formula: '#acc8f8',
          mode: 'raw',
        },
        colors_is_formula: false,
        styles: {},
      },
    }
  },
  computed: {
    rawFormula: {
      get() {
        return this.values.colors.formula
      },
      set(newValue) {
        this.values.colors = {
          ...this.values.colors,
          formula: newValue,
          mode: 'raw',
        }
      },
    },
  },
  methods: {
    setColorsToFormula() {
      this.values.colors_is_formula = true
      this.values.colors = {
        formula: `'${this.values.colors.formula}'`,
        mode: 'simple',
      }
    },
    setColorsToPicker() {
      this.values.colors_is_formula = false
      this.values.colors = {
        formula: '#acc8f8',
        mode: 'raw',
      }
    },
  },
}
</script>
