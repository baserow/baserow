<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      :key="values.variant"
      v-model="values.styles"
      :style-key="values.variant"
      :config-block-types="linkElementBlockTypes"
      :theme="builder.theme"
    />
    <FormGroup
      small-label
      :label="$t('linkElementForm.text')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.value"
        :placeholder="$t('linkElementForm.textPlaceholder')"
      />
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
        :options="linkElementFormVariantOptions"
        type="button"
      >
      </RadioGroup>
    </FormGroup>
  </form>
</template>

<script>
import {
  HORIZONTAL_ALIGNMENTS,
  LINK_VARIANTS,
  WIDTHS_NEW,
} from '@baserow/modules/builder/enums'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import LinkNavigationSelectionForm from '@baserow/modules/builder/components/elements/components/forms/general/LinkNavigationSelectionForm'

import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'

export default {
  name: 'LinkElementForm',
  components: {
    InjectedFormulaInput,
    LinkNavigationSelectionForm,
    CustomStyleButton,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: {},
        alignment: HORIZONTAL_ALIGNMENTS.LEFT,
        variant: LINK_VARIANTS.LINK,
        width: WIDTHS_NEW.AUTO,
        styles: {},
      },
      allowedValues: ['value', 'alignment', 'variant', 'width', 'styles'],
      linkElementFormVariantOptions: [
        {
          value: LINK_VARIANTS.LINK,
          label: this.$t('linkElementForm.variantLink'),
        },
        {
          value: LINK_VARIANTS.BUTTON,
          label: this.$t('linkElementForm.variantButton'),
        },
      ],
    }
  },
  computed: {
    linkElementBlockTypes() {
      return this.values.variant === LINK_VARIANTS.LINK ? ['link'] : ['button']
    },
  },
}
</script>
