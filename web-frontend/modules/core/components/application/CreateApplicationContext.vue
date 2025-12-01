<template>
  <Context
    overflow-scroll
    max-height-if-outside-viewport
    class="create-application-context"
    @shown="fetchRolesAndPermissions"
  >
    <div
      v-if="workspace._.additionalLoading"
      class="loading margin-left-2 margin-top-2 margin-right-2 margin-bottom-2"
    ></div>
    <ul v-else class="context__menu">
      <li
        v-for="applicationType in applicationTypes"
        :key="applicationType.getType()"
        class="context__menu-item"
      >
        <a
          :ref="'createApplicationModalToggle' + applicationType.getType()"
          class="context__menu-item-link context__menu-item-link--with-desc"
          :class="{
            disabled: !canCreateCreateApplication,
          }"
          @click="toggleCreateApplicationModal(applicationType.getType())"
        >
          <span class="context__menu-item-title">
            <i
              class="context__menu-item-icon"
              :class="applicationType.iconClass"
            ></i>
            {{ applicationType.getName()
            }}<DevelopmentBadge
              v-if="applicationType.developmentStage"
              :stage="applicationType.developmentStage"
            ></DevelopmentBadge
          ></span>
          <div
            class="context__menu-item-description context__menu-item-description--offset"
          >
            {{ applicationType.getDescription() }}
          </div>
        </a>
        <CreateApplicationModal
          :ref="'createApplicationModal' + applicationType.getType()"
          :application-type="applicationType"
          :workspace="workspace"
          @created="hide"
        ></CreateApplicationModal>
      </li>
      <li class="context__menu-item">
        <a
          class="context__menu-item-link context__menu-item-link--with-desc"
          :class="{
            disabled: !canCreateCreateApplication,
          }"
          @click="openTemplateModal()"
        >
          <span class="context__menu-item-title">
            <i class="context__menu-item-icon iconoir-page"></i>
            {{ $t('createApplicationContext.fromTemplate') }}</span
          >
          <div
            class="context__menu-item-description context__menu-item-description--offset"
          >
            {{ $t('createApplicationContext.fromTemplateDesc') }}
          </div>
        </a>
        <TemplateModal
          ref="templateModal"
          :workspace="workspace"
        ></TemplateModal>
      </li>
      <li class="context__menu-item">
        <a
          class="context__menu-item-link context__menu-item-link--with-desc"
          :class="{
            disabled: !canCreateCreateApplication,
          }"
          @click="openImportWorkspaceModal()"
        >
          <span class="context__menu-item-title">
            <i class="context__menu-item-icon iconoir-import"></i>
            {{ $t('createApplicationContext.importWorkspace') }}</span
          >
          <div
            class="context__menu-item-description context__menu-item-description--offset"
          >
            {{ $t('createApplicationContext.importWorkspaceDesc') }}
          </div>
        </a>
        <ImportWorkspaceModal
          ref="importWorkspaceModal"
          :workspace="workspace"
        ></ImportWorkspaceModal>
      </li>
    </ul>
  </Context>
</template>

<script>
import CreateApplicationModal from '@baserow/modules/core/components/application/CreateApplicationModal'
import TemplateModal from '@baserow/modules/core/components/template/TemplateModal'
import ImportWorkspaceModal from '@baserow/modules/core/components/import/ImportWorkspaceModal.vue'
import context from '@baserow/modules/core/mixins/context'
import DevelopmentBadge from '@baserow/modules/core/components/DevelopmentBadge'

export default {
  name: 'CreateApplicationContext',
  components: {
    DevelopmentBadge,
    CreateApplicationModal,
    ImportWorkspaceModal,
    TemplateModal,
  },
  mixins: [context],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  computed: {
    applicationTypes() {
      const applicationTypes = this.$registry.getOrderedList('application')

      return applicationTypes.filter((applicationType) =>
        applicationType.canBeCreated()
      )
    },
    canCreateCreateApplication() {
      return this.$hasPermission(
        'workspace.create_application',
        this.workspace,
        this.workspace.id
      )
    },
  },
  methods: {
    async fetchRolesAndPermissions() {
      await this.$store.dispatch('workspace/fetchPermissions', this.workspace)
      await this.$store.dispatch('workspace/fetchRoles', this.workspace)
    },
    openTemplateModal() {
      if (!this.canCreateCreateApplication) {
        return
      }

      this.$refs.templateModal.show()
      this.hide()
    },
    openImportWorkspaceModal() {
      if (!this.canCreateCreateApplication) {
        return
      }

      this.$refs.importWorkspaceModal.show()
      this.hide()
    },
    toggleCreateApplicationModal(type) {
      if (!this.canCreateCreateApplication) {
        return
      }

      const target = this.$refs['createApplicationModalToggle' + type][0]
      this.$refs['createApplicationModal' + type][0].toggle(target)
      this.hide()
    },
  },
}
</script>
