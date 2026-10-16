<template>
  <div style="position: absolute">
    <ApplicationContext
      ref="context"
      :application="application"
      :workspace="workspace"
    >
      <template #additional-context-items>
        <li
          v-if="
            $hasPermission(
              'application.update',
              application,
              application.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            :class="{ 'context__menu-item-link--error': settingsInError }"
            @click="openSettingsModal"
          >
            <i class="context__menu-item-icon iconoir-settings"></i>
            {{ $t('sidebarComponentBuilder.settings') }}
            <i
              v-if="settingsInError"
              v-tooltip="settingsErrorMessage"
              class="context__menu-item-error-icon iconoir-warning-circle"
            ></i>
          </a>
        </li>
      </template>
    </ApplicationContext>

    <BuilderSettingsModal
      ref="builderSettingsModal"
      :builder="application"
      :workspace="workspace"
    />
  </div>
</template>

<script>
import BuilderSettingsModal from '@baserow/modules/builder/components/settings/BuilderSettingsModal'
import ApplicationContext from '@baserow/modules/core/components/application/ApplicationContext.vue'
import applicationContext from '@baserow/modules/core/mixins/applicationContext'

export default {
  components: {
    ApplicationContext,
    BuilderSettingsModal,
  },
  mixins: [applicationContext],
  props: {
    application: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  computed: {
    settingsErrorMessage() {
      for (const setting of this.$registry.getOrderedList('builderSettings')) {
        const message = setting.getErrorMessage(this.application)
        if (message) {
          return message
        }
      }
      return null
    },
    settingsInError() {
      return Boolean(this.settingsErrorMessage)
    },
  },
  methods: {
    openSettingsModal() {
      this.$refs.context.hide()
      this.$refs.builderSettingsModal.show()
    },
  },
}
</script>
