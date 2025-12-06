<template>
  <div :class="positionClasses">
    <template
      v-if="
        mode === 'editing' &&
        children.length === 0 &&
        $hasPermission('builder.page.create_element', currentPage, workspace.id)
      "
    >
      <AddElementZone @add-element="showAddElementModal" />
      <AddElementModal ref="addElementModal" :page="elementPage" />
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
import AddElementZone from '@baserow/modules/builder/components/elements/AddElementZone'
import containerElement from '@baserow/modules/builder/mixins/containerElement'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal'
import ElementPreview from '@baserow/modules/builder/components/elements/ElementPreview'
import PageElement from '@baserow/modules/builder/components/page/PageElement'

export default {
  name: 'PositionedContainerElement',
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

  computed: {
    positionClasses() {
      const alignment = this.element.alignment || 'top'
      const behaviour = this.element.behaviour || 'fixed'

      return {
        'positioned-container': true,
        'position-fixed': behaviour === 'fixed',
        'position-top': alignment === 'top',
        'position-bottom': alignment === 'bottom',
      }
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

<style scoped>
.position-fixed {
  position: fixed;
  left: 0;
  right: 0;
  z-index: 1000;
}

.position-top {
  top: 0;
}

.position-bottom {
  bottom: 0;
}

.positioned-container {
  width: 100%;
  background: inherit;
}
</style>
