<template>
  <div>
    <template v-if="mode === 'editing' && children.length === 0">
      <AddElementZone
        :disabled="
          !$hasPermission(
            'builder.page.create_element',
            currentPage,
            workspace.id
          )
        "
        :parent-element="element"
        @add-element="showAddElementModal"
      ></AddElementZone>
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
import {
  ElementPreview,
  AddElementZone,
  AddElementModal,
} from '@baserow/modules/builder/components/editorRendering'

import containerElement from '@baserow/modules/builder/mixins/containerElement'
import PageElement from '@baserow/modules/builder/components/page/PageElement'

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
    element: {
      type: Object,
      required: true,
    },
  },
  emits: ['move'],
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
