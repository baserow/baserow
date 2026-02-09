<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('linkFieldForm.fieldLinkNameLabel')"
      class="margin-bottom-2"
      required
      horizontal
    >
      <InjectedFormulaInput
        v-model="values.link_name"
        :placeholder="$t('linkFieldForm.fieldLinkNamePlaceholder')"
      />
      <template #after-input>
        <CustomStyleButton
          :key="values.variant"
          v-model="values.styles"
          style-key="cell"
          :config-block-types="linkFieldBlockTypes"
          :theme="baseTheme"
          :on-styles-changed="onFieldStylesChanged"
          :extra-args="{ onlyCell: true, noAlignment: true }"
          variant="normal"
        />
      </template>
    </FormGroup>
    <LinkNavigationSelectionForm
      :default-values="defaultValues"
      @values-changed="emitChange($event)"
    />
    <FormGroup
      :label="$t('linkElementForm.variant')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="values.variant"
        :options="LINK_VARIANTS"
        type="button"
      />
    </FormGroup>
  </form>
</template>

<script>
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import LinkNavigationSelectionForm from '@baserow/modules/builder/components/elements/components/forms/general/LinkNavigationSelectionForm'
import { LINK_VARIANTS } from '@baserow/modules/builder/enums'

export default {
  name: 'LinkField',
  components: {
    InjectedFormulaInput,
    CustomStyleButton,
    LinkNavigationSelectionForm,
  },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['link_name', 'styles', 'variant'],
      values: {
        link_name: {},
        styles: {},
        variant: LINK_VARIANTS.LINK,
      },
    }
  },
  computed: {
    linkFieldBlockTypes() {
      const defaultBlocks = ['table']
      if (this.values.variant === LINK_VARIANTS.LINK) {
        return [...defaultBlocks, 'link']
      } else {
        return [...defaultBlocks, 'button']
      }
    },
    LINK_VARIANTS() {
      return [
        {
          value: LINK_VARIANTS.LINK,
          label: this.$t('linkElementForm.variantLink'),
        },
        {
          value: LINK_VARIANTS.BUTTON,
          label: this.$t('linkElementForm.variantButton'),
        },
      ]
    },
  },
}
</script>
