<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('simpleContainerElementForm.behaviourLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="values.behaviour"
        :options="behaviourTypes"
        type="button"
      />
    </FormGroup>
  </form>
</template>

<script>
import { mapGetters } from 'vuex'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { PAGE_ELEMENT_BEHAVIOURS } from '@baserow/modules/builder/enums'

export default {
  name: 'SimpleContainerElementForm',
  mixins: [elementForm],
  data() {
    return {
      values: {
        alignment: '',
        behaviour: '',
        styles: {},
      },
      allowedValues: ['alignment', 'behaviour', 'styles'],
    }
  },
  computed: {
    ...mapGetters({
      getRootElements: 'element/getRootElements',
      getElementSelected: 'element/getSelected',
    }),
    element() {
      return this.getElementSelected(this.builder)
    },
    rootElements() {
      return this.getRootElements(this.currentPage)
    },
    behaviourTypes() {
      return [
        {
          label: this.$t('pageElementBehaviour.normal'),
          value: PAGE_ELEMENT_BEHAVIOURS.NORMAL,
        },
        {
          label: this.$t('pageElementBehaviour.sticky'),
          value: PAGE_ELEMENT_BEHAVIOURS.STICKY,
        },
      ]
    },
  },
  methods: {},
}
</script>
