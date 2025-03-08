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

export default {
  name: 'SimpleContainerElement',
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
     * @property submit_button_label - The label of the submit button
     * @property reset_initial_values_post_submission - Whether to reset the form
     *  elements to their initial value or not, following a successful submission.
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {},
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
