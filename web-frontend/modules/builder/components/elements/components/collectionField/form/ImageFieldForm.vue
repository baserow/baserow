<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('imageFieldForm.fieldSrcLabel')"
      class="margin-bottom-2"
      horizontal
      required
    >
      <InjectedFormulaInput
        v-model="values.src"
        :placeholder="$t('imageFieldForm.fieldSrcPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('imageFieldForm.fieldAltLabel')"
      :helper-text="$t('imageFieldForm.fieldAltHelp')"
      class="margin-bottom-2"
      horizontal
      required
    >
      <InjectedFormulaInput
        v-model="values.alt"
        :placeholder="$t('imageFieldForm.fieldAltPlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'ImageFieldForm',
  components: { InjectedFormulaInput },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['src', 'alt', 'styles'],
      values: {
        src: {},
        alt: {},
        styles: {},
      },
    }
  },
}
</script>
