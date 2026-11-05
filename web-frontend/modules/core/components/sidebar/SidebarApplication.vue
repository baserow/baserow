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
        @click="$emit('selected', application)"
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
        @click="toggleContext"
        @mousedown.stop
      >
        <i class="baserow-icon-more-vertical"></i>
      </a>

      <component
        :is="getApplicationContextComponent(application)"
        v-if="contextRequested || bundleLoaded"
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
import { nextTick } from 'vue'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { isApplicationBundleLoaded } from '@baserow/modules/core/utils/applicationBundles'
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
  emits: ['selected'],
  data() {
    return {
      deleting: false,
      contextRequested: false,
    }
  },
  computed: {
    bundleLoaded() {
      return isApplicationBundleLoaded(this.$nuxt, this.application.type)
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
  methods: {
    /** Load hidden application controls on demand and report download failures. */
    async toggleContext() {
      try {
        if (!this.bundleLoaded) {
          await this.applicationType.load()
          this.contextRequested = true
          await nextTick()
        }
        this.$refs.context.toggle(this.$refs.contextLink, 'bottom', 'right', 0)
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
