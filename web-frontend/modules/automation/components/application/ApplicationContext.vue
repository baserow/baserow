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
              class="context__menu-item-error-icon iconoir-warning-circle"
            ></i>
          </a>
        </li>
      </template>
    </ApplicationContext>

    <AutomationSettingsModal
      ref="automationSettingsModal"
      :automation="application"
    />
  </div>
</template>

<script>
import { defineComponent, ref, computed, toRefs } from 'vue'
import AutomationSettingsModal from '@baserow/modules/automation/components/settings/AutomationSettingsModal'
import ApplicationContext from '@baserow/modules/core/components/application/ApplicationContext'
import applicationContext from '@baserow/modules/core/mixins/applicationContext'

export default defineComponent({
  components: {
    ApplicationContext,
    AutomationSettingsModal,
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
  setup(props) {
    const { application } = toRefs(props)
    const app = useNuxtApp()
    const context = ref(null)
    const automationSettingsModal = ref(null)

    const openSettingsModal = () => {
      automationSettingsModal.value.show()
      context.value.hide()
    }

    const settingsInError = computed(() =>
      app.$registry
        .getOrderedList('automationSettings')
        .some((setting) => setting.isInError(application.value))
    )

    return {
      context,
      automationSettingsModal,
      openSettingsModal,
      settingsInError,
    }
  },
})
</script>
