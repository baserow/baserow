<template>
  <FunctionalGridViewFieldArray
    :field="field"
    :value="value"
    :row="row"
    :selected="selected"
    v-on="$listeners"
    @show="showModal"
  >
    <!--
    This modal has to be added as slot because the component must have the
    `FunctionalGridViewFieldArray` component as root element.
    -->
    <component
      :is="modalComponent"
      v-if="needsModal"
      ref="modal"
      :read-only="true"
      :value="value"
    ></component>
  </FunctionalGridViewFieldArray>
</template>

<script>
import FunctionalGridViewFieldArray from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldArray'
import gridField from '@baserow/modules/database/mixins/gridField'
import FileFieldModal from '@baserow/modules/database/components/field/FileFieldModal.vue'
import { isElement } from '@baserow/modules/core/utils/dom'
import arrayLoading from '@baserow/modules/database/mixins/arrayLoading'

export default {
  name: 'GridViewFieldArray',
  components: { FileFieldModal, FunctionalGridViewFieldArray },
  mixins: [gridField, arrayLoading],
  props: {
    selected: {
      type: Boolean,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    subType() {
      return this.$registry.get('formula_type', this.field.array_formula_type)
    },
    modalComponent() {
      return this.subType.getExtraModal()
    },
    needsModal() {
      return this.modalComponent !== null
    },
  },
  methods: {
    showModal() {
      this.$refs.modal?.show()
    },
    canSelectNext() {
      return !this.needsModal || !this.$refs.modal.open
    },
    canKeyDown() {
      return !this.needsModal || !this.$refs.modal.open
    },
    canKeyboardShortcut() {
      return !this.needsModal || !this.$refs.modal.open
    },
    canUnselectByClickingOutside(event) {
      return (
        !this.needsModal ||
        ((!this.$refs.modal ||
          !isElement(this.$refs.modal.$el, event.target)) &&
          !isElement(this.$refs.modal.$el, event.target))
      )
    },
  },
}
</script>
