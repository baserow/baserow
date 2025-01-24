<template>
  <Modal
    ref="modal"
    class="select-row-modal"
    box-class="select-row-modal__box"
    @hidden="$emit('hidden')"
  >
    <!--
    Because of how the moveToBody mixin works it takes a small moment before the $refs
    become available. In order for the Scrollbars components to work the refs need to
    be available right away. That is the reason why the contents of the SelectRowModal
    have been moved to a separate component.
    -->
    <SelectRowContent
      :table-id="tableId"
      :view-id="viewId"
      :value="value"
      :multiple="multiple"
      :new-row-presets="newRowPresets"
      :persistent-field-options-key="persistentFieldOptionsKey"
      @selected="selected"
      @unselected="unselected"
      @hide="hide"
    ></SelectRowContent>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

import SelectRowContent from './SelectRowContent'

export default {
  name: 'SelectRowModal',
  components: { SelectRowContent },
  mixins: [modal],
  props: {
    tableId: {
      type: Number,
      required: true,
    },
    viewId: {
      type: [Number, null],
      required: false,
      default: null,
    },
    value: {
      type: Array,
      required: false,
      default: () => [],
    },
    multiple: {
      type: Boolean,
      required: false,
      default: false,
    },
    newRowPresets: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    /**
     * If provided then the changed field options are saved into local storage. If a
     * user for example changes the field width, then that's stored in local storage so
     * that when the row modal is opened, it's visible.
     */
    persistentFieldOptionsKey: {
      type: String,
      required: false,
      default: '',
    },
  },
  methods: {
    /**
     * Hide the modal when a row has been selected.
     */
    selected(...args) {
      if (!this.multiple) {
        this.hide()
      }
      this.$emit('selected', ...args)
    },
    unselected(...args) {
      this.$emit('unselected', ...args)
    },
  },
}
</script>
