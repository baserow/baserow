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

    <FormGroup
      v-if="values.behaviour === pageBehaviours.FIXED"
      small-label
      required
      :label="$t('simpleContainerElementForm.alignmentLabel')"
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.alignment" :show-search="false">
        <DropdownItem
          v-for="alignment in alignmentTypes"
          :key="alignment.value"
          :name="alignment.label"
          :value="alignment.value"
        />
      </Dropdown>

      <Alert>
        <slot name="title">{{
          $t('simpleContainerElementForm.fixedHintTitle')
        }}</slot>
        <p>{{ $t('simpleContainerElementForm.fixedHintMessage') }}</p>
      </Alert>
    </FormGroup>
  </form>
</template>

<script>
import { mapGetters } from 'vuex'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import {
  PAGE_ALIGNMENT_BEHAVIOURS,
  PAGE_ALIGNMENTS,
} from '@baserow/modules/builder/enums'

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
    pageBehaviours() {
      return PAGE_ALIGNMENT_BEHAVIOURS
    },
    behaviourTypes() {
      return [
        {
          label: this.$t('simpleContainerElementForm.behaviourNormal'),
          value: PAGE_ALIGNMENT_BEHAVIOURS.NORMAL,
        },
        {
          label: this.$t('simpleContainerElementForm.behaviourFixed'),
          value: PAGE_ALIGNMENT_BEHAVIOURS.FIXED,
        },
      ]
    },
    alignmentTypes() {
      return [
        {
          label: this.$t('simpleContainerElementForm.alignmentTop'),
          value: PAGE_ALIGNMENTS.TOP,
        },
        {
          label: this.$t('simpleContainerElementForm.alignmentBottom'),
          value: PAGE_ALIGNMENTS.BOTTOM,
        },
      ]
    },
  },
  methods: {},
}
</script>
