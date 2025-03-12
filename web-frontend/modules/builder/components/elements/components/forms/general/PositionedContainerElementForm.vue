<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      required
      :label="$t('positionedContainerElementForm.alignmentLabel')"
      class="margin-bottom-2"
    >
      <Dropdown
        :value="values.alignment"
        :show-search="false"
        @input="onAlignmentChanged"
      >
        <DropdownItem
          v-for="alignment in alignmentTypes"
          :key="alignment.value"
          :name="alignment.label"
          :value="alignment.value"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup
      :label="$t('positionedContainerElementForm.behaviourLabel')"
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
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapActions, mapGetters } from 'vuex'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import {
  PAGE_ALIGNMENT_BEHAVIOURS,
  PAGE_ALIGNMENTS,
} from '@baserow/modules/builder/enums'

export default {
  name: 'PositionedContainerElementForm',
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
    alignmentTypes() {
      return [
        {
          label: this.$t('positionedContainerElementForm.alignmentTop'),
          value: PAGE_ALIGNMENTS.TOP,
        },
        {
          label: this.$t('positionedContainerElementForm.alignmentBottom'),
          value: PAGE_ALIGNMENTS.BOTTOM,
        },
      ]
    },
    behaviourTypes() {
      return [
        {
          label: this.$t('positionedContainerElementForm.behaviourFixed'),
          value: PAGE_ALIGNMENT_BEHAVIOURS.FIXED,
        },
        {
          label: this.$t('positionedContainerElementForm.behaviourSticky'),
          value: PAGE_ALIGNMENT_BEHAVIOURS.STICKY,
        },
      ]
    },
  },
  methods: {
    ...mapActions({
      actionMoveElement: 'element/move',
    }),
    /**
     * The Positioned Container is only allowed at the top or bottom of the
     * page. When the alignment is changed, the following happens:
     *
     * - Element is moved to the first or last position.
     * - The `alignment` property is updated to ensure that the correct CSS
     *   classes are applied.
     */
    async onAlignmentChanged(event) {
      let beforeElementId = null
      if (event === PAGE_ALIGNMENTS.TOP) {
        beforeElementId = this.rootElements.at(0).id
      }

      try {
        await this.actionMoveElement({
          builder: this.builder,
          page: this.currentPage,
          elementId: this.element.id,
          beforeElementId,
        })
        this.values.alignment = event
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
