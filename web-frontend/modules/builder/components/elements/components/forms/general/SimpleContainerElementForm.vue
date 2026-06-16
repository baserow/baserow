<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      v-if="isRootContainer"
      :label="$t('simpleContainerElementForm.behaviourLabel')"
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
    isRootContainer() {
      return !this.defaultValues.parent_element_id
    },
    behaviourOptions() {
      return [
        {
          label: this.$t('pageElementBehaviour.normal'),
          value: PAGE_ELEMENT_BEHAVIOURS.NORMAL,
        },
        {
          label: this.$t('pageElementBehaviour.sticky'),
          value: PAGE_ELEMENT_BEHAVIOURS.STICKY,
        },
        {
          label: this.$t('pageElementBehaviour.fixed'),
          value: PAGE_ELEMENT_BEHAVIOURS.FIXED,
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
