<template>
  <li
    class="tree__item"
    :class="{
      'tree__item--loading': application._.loading,
    }"
  >
    <div
      class="tree__action tree__action--has-options"
      :class="{ 'tree__action--highlighted': highlighted }"
      data-sortable-handle
      :data-highlight="`sidebar-application-${application.id}`"
    >
      <a
        class="tree__link"
        :class="{ 'tree__link--empty': application.name === '' }"
        :title="application.name"
        :aria-label="application.name"
        @click="$emit('selected', application)"
      >
        <i class="tree__icon" :class="application._.type.iconClass"></i>
        <span class="tree__link-text">
          <template v-if="application.name === ''">&nbsp;</template>
          <Editable
            ref="rename"
            :value="application.name"
            @change="renameApplication(application, $event)"
          ></Editable>
        </span>
      </a>

      <a
        ref="contextLink"
        class="tree__options"
        @click="$refs.context.toggle($refs.contextLink, 'bottom', 'right', 0)"
        @mousedown.stop
      >
        <i class="baserow-icon-more-vertical"></i>
      </a>

      <component
        :is="getApplicationContextComponent(application)"
        ref="context"
        :application="application"
        :workspace="workspace"
        @rename="handleRenameApplication()"
      ></component>

      <TrashModal
        ref="applicationTrashModal"
        :initial-workspace="workspace"
        :initial-application="application"
      >
      </TrashModal>
    </div>
    <slot name="body"></slot>
  </li>
</template>

<script>
import SidebarDuplicateApplicationContextItem from '@baserow/modules/core/components/sidebar/SidebarDuplicateApplicationContextItem.vue'
import TrashModal from '@baserow/modules/core/components/trash/TrashModal'
import SnapshotsModal from '@baserow/modules/core/components/snapshots/SnapshotsModal'
import application from '@baserow/modules/core/mixins/application'

export default {
  name: 'SidebarApplication',
  components: {
    TrashModal,
    SidebarDuplicateApplicationContextItem,
    SnapshotsModal,
  },
  mixins: [application],
  props: {
    application: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
    highlighted: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      deleting: false,
    }
  },
  computed: {
    additionalContextComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .reduce(
          (components, plugin) =>
            components.concat(
              plugin.getAdditionalApplicationContextComponents(
                this.workspace,
                this.application
              )
            ),
          []
        )
        .filter((component) => component !== null)
    },
    applicationType() {
      return this.$registry.get('application', this.application.type)
    },
  },
}
</script>
