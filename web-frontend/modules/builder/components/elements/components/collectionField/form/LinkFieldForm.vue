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
import LinkNavigationSelectionForm from '@baserow/modules/builder/components/elements/components/forms/general/LinkNavigationSelectionForm'
import { LINK_VARIANTS } from '@baserow/modules/builder/enums'

export default {
  name: 'LinkField',
  components: {
    InjectedFormulaInput,
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
