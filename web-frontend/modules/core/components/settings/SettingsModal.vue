<template>
  <ModalV2 left-sidebar>
    <template #header-content>
      <h2>{{ currentSetting.getName() }}</h2>
    </template>
    <template #sidebar-content>
      <div class="modal-sidebar__head">
        <Avatar
          rounded
          :initials="name | nameAbbreviation"
          size="large"
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
      <component
        :is="settingPageComponent"
        ref="settingPageComponent"
        @loading="loading = $event"
        @database-token-page-type-changed="setDatabaseTokenPageType"
      ></component>
    </template>

    <template #footer-content>
      <Button
        v-if="page === 'tokens' && dbTokenPageType === 'create'"
        type="secondary"
        @click="$refs.settingPageComponent.setPageType('list')"
      >
        {{ $t('action.cancel') }}
      </Button>
      <Button
        :type="getButtonType(page)"
        :loading="loading"
        :disabled="loading"
        @click="submit"
      >
        {{ buttonLabel }}
      </Button>
    </template>
  </ModalV2>
</template>

<script>
import { mapGetters } from 'vuex'

import modalv2 from '@baserow/modules/core/mixins/modalv2'

import PasswordSettings from '@baserow/modules/core/components/settings/PasswordSettings'

export default {
  name: 'SettingsModal',
  components: { PasswordSettings },
  mixins: [modalv2],
  data() {
    return {
      page: null,
      currentSetting: null,
      loading: false,
      buttonLabel: '',
      dbTokenPageType: 'list',
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
  watch: {
    page(newVal) {
      this.currentSetting = Object.values(
        this.$registry.getAll('settings')
      ).find((setting) => setting.type === newVal)
    },
    settingPageComponent(newVal) {
      this.$nextTick(() => {
        this.buttonLabel = this.$refs.settingPageComponent.getCTALabel()
      })
    },
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
      return modalv2.methods.show.call(this, ...args)
    },
    submit() {
      if (this.page === 'tokens' && this.dbTokenPageType === 'list')
        this.$refs.settingPageComponent.setPageType('create')
      else this.$refs.settingPageComponent.submitForm()
    },
    setDatabaseTokenPageType(pageType) {
      this.dbTokenPageType = pageType
    },
    getButtonType(page) {
      if (page === 'delete-account') return 'danger'
      return 'primary'
    },
  },
}
</script>
