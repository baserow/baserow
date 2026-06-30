<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('simpleContainerElementForm.behaviourLabel')"
      :helper-text="positioningHelperText"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="values.behaviour"
        :options="behaviourOptions"
        type="button"
      />
    </FormGroup>
    <FormGroup
      v-if="
        isRootContainer && values.behaviour !== PAGE_ELEMENT_BEHAVIOURS.NORMAL
      "
      :label="$t('simpleContainerElementForm.alignmentLabel')"
      small-label
      required
    >
      <RadioGroup
        v-model="values.alignment"
        :options="alignmentOptions"
        type="button"
      />
    </FormGroup>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import {
  PAGE_ELEMENT_ALIGNMENTS,
  PAGE_ELEMENT_BEHAVIOURS,
} from '@baserow/modules/builder/enums'

export default {
  name: 'SimpleContainerElementForm',
  mixins: [elementForm],
  data() {
    return {
      values: {
        behaviour: PAGE_ELEMENT_BEHAVIOURS.NORMAL,
        alignment: PAGE_ELEMENT_ALIGNMENTS.TOP,
        styles: {},
      },
      allowedValues: ['behaviour', 'alignment', 'styles'],
    }
  },
  computed: {
    PAGE_ELEMENT_BEHAVIOURS: () => PAGE_ELEMENT_BEHAVIOURS,
    parentElement() {
      const getParent = this.$store?.getters?.['element/getParent']
      if (
        typeof getParent !== 'function' ||
        !this.elementPage ||
        !this.defaultValues?.id
      ) {
        return null
      }

      return getParent(this.elementPage, this.defaultValues)
    },
    isRootContainer() {
      return !this.parentElement && !this.defaultValues.parent_element_id
    },
    disablePositioningControls() {
      return !this.isRootContainer
    },
    positioningHelperText() {
      return this.disablePositioningControls
        ? this.$t('simpleContainerElementForm.rootContainerOnlyHelper')
        : null
    },
    behaviourOptions() {
      return [
        {
          label: this.$t('pageElementBehaviour.normal'),
          value: PAGE_ELEMENT_BEHAVIOURS.NORMAL,
          disabled: this.disablePositioningControls,
        },
        {
          label: this.$t('pageElementBehaviour.sticky'),
          value: PAGE_ELEMENT_BEHAVIOURS.STICKY,
          disabled: this.disablePositioningControls,
        },
        {
          label: this.$t('pageElementBehaviour.fixed'),
          value: PAGE_ELEMENT_BEHAVIOURS.FIXED,
          disabled: this.disablePositioningControls,
        },
      ]
    },
    alignmentOptions() {
      return [
        {
          label: this.$t('pageElementAlignment.top'),
          value: PAGE_ELEMENT_ALIGNMENTS.TOP,
        },
        {
          label: this.$t('pageElementAlignment.bottom'),
          value: PAGE_ELEMENT_ALIGNMENTS.BOTTOM,
        },
      ]
    },
  },
}
</script>
