<template>
  <ApplicationContext
    ref="context"
    :application="application"
    :workspace="workspace"
  >
    <template #additional-context-items>
      <li class="context__menu-item">
        <nuxt-link
          :to="{
            name: 'database-api-docs-detail',
            params: {
              databaseId: application.id,
            },
          }"
          class="context__menu-item-link"
        >
          <i class="context__menu-item-icon iconoir-book"></i>
          {{ $t('sidebar.viewAPI') }}
        </nuxt-link>
      </li>
      <li
        v-if="
          $hasPermission(
            'application.update_lock',
            application,
            application.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="toggleDatabaseLock">
          <i class="context__menu-item-icon iconoir-lock"></i>
          {{
            application.locked
              ? $t('sidebarApplication.unlock')
              : $t('sidebarApplication.lock')
          }}
        </a>
      </li>
    </template>
  </ApplicationContext>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import ApplicationContext from '@baserow/modules/core/components/application/ApplicationContext.vue'
import applicationContext from '@baserow/modules/core/mixins/applicationContext'

export default {
  components: {
    ApplicationContext,
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
  methods: {
    async toggleDatabaseLock() {
      this.$refs.context.hide()
      this.$store.dispatch('application/setItemLoading', {
        application: this.application,
        value: true,
      })

      try {
        await this.$store.dispatch('application/update', {
          application: this.application,
          values: {
            locked: !this.application.locked,
          },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }

      this.$store.dispatch('application/setItemLoading', {
        application: this.application,
        value: false,
      })
    },
  },
}
</script>
