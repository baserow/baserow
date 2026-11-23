<template>
  <li
    class="tree__item"
    :class="{
      'tree__item--loading': application._?.loading,
    }"
  >
    <div
      class="tree__action tree__action--has-options"
      :class="{
        'tree__action--highlighted': highlighted,
        'tree__action--error': isInError,
      }"
      data-sortable-handle
      :data-highlight="`sidebar-application-${application.id}`"
    >
      <a
        class="tree__link"
        :class="{ 'tree__link--empty': application.name === '' }"
        :title="application.name"
        :aria-label="application.name"
        :aria-expanded="$slots.body ? bodyExpanded : undefined"
        @click="onTitleClick"
      >
        <i class="tree__icon" :class="application._?.type?.iconClass"></i>
        <span class="tree__link-text">
          <template v-if="application.name === ''">&nbsp;</template>
          <Editable
            ref="rename"
            :value="application.name"
            @change="renameApplication(application, $event)"
          ></Editable>
        </span>
        <i
          v-if="isInError"
          v-tooltip="errorMessage"
          class="tree__error-icon iconoir-warning-circle"
        ></i>
      </a>

      <a
        ref="contextLink"
        class="tree__options"
        @click="$refs.context.toggle($refs.contextLink, 'bottom', 'right', 0)"
        @mousedown.stop
      >
        <i class="baserow-icon-more-vertical"></i>
      </a>

      <BadgeCounter
        v-if="application.pending_count > 0"
        class="tree__counter badge-counter--warning"
        :count="application.pending_count"
      />

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
    <Transition
      name="tree-group"
      @before-leave="(element) => (element.inert = true)"
    >
      <div
        v-if="$slots.body && (bodyExpanded || isApplicationSelected)"
        class="tree__group"
        :class="{ 'tree__group--collapsed': !bodyExpanded }"
        :inert="!bodyExpanded ? '' : null"
      >
        <div class="tree__group-content">
          <slot name="body"></slot>
        </div>
      </div>
    </Transition>
  </li>
</template>

<script>
import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'
import SidebarDuplicateApplicationContextItem from '@baserow/modules/core/components/sidebar/SidebarDuplicateApplicationContextItem.vue'
import TrashModal from '@baserow/modules/core/components/trash/TrashModal'
import SnapshotsModal from '@baserow/modules/core/components/snapshots/SnapshotsModal'
import application from '@baserow/modules/core/mixins/application'

export default {
  name: 'SidebarApplication',
  components: {
    BadgeCounter,
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
  emits: ['selected'],
  data() {
    return {
      deleting: false,
    }
  },
  computed: {
    bodyExpanded: {
      get() {
        return (
          this.$store.state.application.expandedSidebarApplications[
            this.application.id
          ] === this.workspace.id
        )
      },
      set(expanded) {
        this.$store.commit('application/SET_SIDEBAR_EXPANDED', {
          id: this.application.id,
          workspaceId: this.workspace.id,
          expanded,
        })
      },
    },
    isApplicationSelected() {
      return this.$store.getters['application/isSelected'](this.application)
    },
    additionalContextComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .reduce((components, plugin) => {
          return components.concat(
            plugin.getAdditionalApplicationContextComponents(
              this.workspace,
              this.application
            )
          )
        }, [])
        .filter((component) => component !== null)
    },
    applicationType() {
      return this.$registry.get('application', this.application.type)
    },
    errorMessage() {
      return this.applicationType.getErrorMessage(this.application)
    },
    isInError() {
      return Boolean(this.errorMessage)
    },
  },
  watch: {
    isApplicationSelected: {
      immediate: true,
      handler(selected) {
        if (selected && this.$slots.body) {
          this.bodyExpanded = true
        }
      },
    },
  },
  beforeUnmount() {
    this.bodyExpanded = false
  },
  methods: {
    onTitleClick(event) {
      if (event.target.isContentEditable) {
        return
      }
      if (this.$slots.body) {
        this.bodyExpanded = !this.bodyExpanded
      } else {
        this.$emit('selected', this.application)
      }
    },
  },
}
</script>
