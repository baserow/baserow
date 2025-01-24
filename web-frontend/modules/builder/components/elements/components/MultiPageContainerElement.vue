<template>
  <div>
    <template
      v-if="
        mode === 'editing' &&
        children.length === 0 &&
        $hasPermission('builder.page.create_element', currentPage, workspace.id)
      "
    >
      <AddElementZone @add-element="showAddElementModal"></AddElementZone>
      <AddElementModal
        ref="addElementModal"
        :page="elementPage"
      ></AddElementModal>
    </template>
    <template v-else>
      <template v-for="child in children">
        <ElementPreview
          v-if="mode === 'editing'"
          :key="child.id"
          :element="child"
          @move="$emit('move', $event)"
        />
        <PageElement
          v-else
          :key="`${child.id}else`"
          :element="child"
          :mode="mode"
        />
      </template>
    </template>
  </div>
</template>

<script>
import AddElementZone from '@baserow/modules/builder/components/elements/AddElementZone.vue'
import containerElement from '@baserow/modules/builder/mixins/containerElement'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal.vue'
import ElementPreview from '@baserow/modules/builder/components/elements/ElementPreview.vue'
import PageElement from '@baserow/modules/builder/components/page/PageElement.vue'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'MultiPageContainerElement',
  components: {
    PageElement,
    ElementPreview,
    AddElementModal,
    AddElementZone,
  },
  mixins: [containerElement],
  props: {
    /**
     * @type {Object}
     * @property page_position - [header|footer|left|right]
     *   Position of this element on the page.
     * @property behaviour - [scroll|fixed|sticky]
     *   How this element follow the scroll of the page.
     * @property shared_type - [all_pages|only_pages|except_pages] Type of share
     * @property pages - List of pages the element is visible or excluded depending on
     *   the share_type.
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    submitButtonLabelResolved() {
      return ensureString(this.resolveFormula(this.element.submit_button_label))
    },
  },
  methods: {
    showAddElementModal() {
      this.$refs.addElementModal.show({
        placeInContainer: null,
        parentElementId: this.element.id,
      })
    },
  },
}
</script>
