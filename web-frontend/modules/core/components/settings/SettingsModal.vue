<template>
  <Modal :left-sidebar="true" :left-sidebar-scrollable="true">
    <template #sidebar>
      <div class="modal-sidebar__head">
        <Avatar
          rounded
          :initials="name | nameAbbreviation"
          size="medium"
        ></Avatar>
        <div class="modal-sidebar__head-name">
          {{ $t('settingsModal.title') }}
        </div>
      </div>
      <ul class="modal-sidebar__nav">
        <li v-for="setting in registeredSettings" :key="setting.type">
          <a
            class="modal-sidebar__nav-link"
            :class="{ active: page === setting.type }"
            @click="setPage(setting.type)"
          >
            <i class="modal-sidebar__nav-icon" :class="setting.iconClass"></i>
            {{ setting.getName() }}
          </a>
        </li>
      </ul>
    </template>
    <template #content>
      <component :is="settingPageComponent"></component>
    </template>
  </Modal>
</template>

<script>
import { mapGetters } from 'vuex'

import modal from '@baserow/modules/core/mixins/modal'

import PasswordSettings from '@baserow/modules/core/components/settings/PasswordSettings'

export default {
  name: 'SettingsModal',
  components: { PasswordSettings },
  mixins: [modal],
  data() {
    return {
      page: null,
    }
  },
  computed: {
    registeredSettings() {
      return this.$registry
        .getOrderedList('settings')
        .filter((settings) => settings.isEnabled() === true)
    },
    settingPageComponent() {
      const active = Object.values(this.$registry.getAll('settings')).find(
        (setting) => setting.type === this.page
      )
      return active ? active.getComponent() : null
    },
    ...mapGetters({
      name: 'auth/getName',
    }),
  },
  async mounted() {
    await this.$store.dispatch('authProvider/fetchLoginOptions')
  },
  methods: {
    setPage(page) {
      this.page = page
    },
    isPage(page) {
      return this.page === page
    },
    show(page = null, ...args) {
      if (page === null) {
        const settings = Object.values(this.$registry.getAll('settings'))
        this.page = settings.length > 0 ? settings[0].type : ''
      } else {
        this.page = page
      }
      return modal.methods.show.call(this, ...args)
    },
  },
}
</script>
