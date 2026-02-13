<template>
  <FunctionalGridViewFieldArray
    ref="cell"
    :field="field"
    :value="value"
    :row="row"
    :selected="selected"
    v-bind="forwarded"
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
import { isElement } from '@baserow/modules/core/utils/dom'
import arrayLoading from '@baserow/modules/database/mixins/arrayLoading'

export default {
  name: 'GridViewFieldArray',
  components: { FunctionalGridViewFieldArray },
  mixins: [gridField, arrayLoading],
  inheritAttrs: false,
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
    forwarded() {
      const { onShow, ...rest } = this.$attrs
      return {
        ...rest,
        onShow: (...args) => {
          this.showModal(...args)
        },
      }
    },
  },
  methods: {
    showModal(index) {
      this.$refs.modal?.show(index)
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
