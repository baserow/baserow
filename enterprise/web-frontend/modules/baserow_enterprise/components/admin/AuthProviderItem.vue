<template>
  <div class="auth-provider-admin__item">
    <AuthProviderIcon :icon="getIcon()" />
    <div class="auth-provider-admin__item-name">
      {{ getName() }}
    </div>
    <div class="auth-provider-admin__item-menu">
      <a
        v-if="hasContextMenu(authProvider.type)"
        ref="editMenuContextLink"
        @click="openContext()"
      >
        <i
          class="baserow-icon-more-vertical auth-provider-admin__item-menu-options"
        ></i>
      </a>
      <EditAuthProviderMenuContext
        v-if="hasContextMenu(authProvider.type)"
        ref="editMenuContext"
        :auth-provider="authProvider"
        @edit="showUpdateSettingsModal"
        @delete="showDeleteModal"
      />
      <UpdateSettingsAuthProviderModal
        v-if="canBeEdited(authProvider.type)"
        ref="updateSettingsModal"
        :auth-provider="authProvider"
        @settings-updated="onSettingsUpdated"
        @cancel="$refs.updateSettingsModal.hide()"
      />
      <DeleteAuthProviderModal
        v-if="canBeDeleted(authProvider.type)"
        ref="deleteModal"
        :auth-provider="authProvider"
        @delete-confirmed="onDeleteConfirmed"
        @cancel="$refs.deleteModal.hide()"
      />
    </div>
    <SwitchInput
      class="auth-provider-admin__item-toggle"
      small
      :value="authProvider.enabled"
      :disabled="isOneProviderEnabled && authProvider.enabled"
      @input="setEnabled($event)"
    ></SwitchInput>
  </div>
</template>

<script>
import SwitchInput from '@baserow/modules/core/components/SwitchInput.vue'
import EditAuthProviderMenuContext from '@baserow_enterprise/components/admin/contexts/EditAuthProviderMenuContext.vue'
import UpdateSettingsAuthProviderModal from '@baserow_enterprise/components/admin/modals/UpdateSettingsAuthProviderModal.vue'
import DeleteAuthProviderModal from '@baserow_enterprise/components/admin/modals/DeleteAuthProviderModal.vue'
import AuthProviderIcon from '@baserow_enterprise/components/AuthProviderIcon.vue'
import authProviderItemMixin from '@baserow_enterprise/mixins/authProviderItemMixin'

export default {
  name: 'AuthProviderItem',
  components: {
    SwitchInput,
    DeleteAuthProviderModal,
    EditAuthProviderMenuContext,
    UpdateSettingsAuthProviderModal,
    AuthProviderIcon,
  },
  mixins: [authProviderItemMixin],
  props: {
    authProvider: {
      type: Object,
      required: true,
    },
  },
  computed: {
    isOneProviderEnabled() {
      return this.$store.getters['authProviderAdmin/isOneProviderEnabled']
    },
  },
  methods: {
    getIcon() {
      return this.$registry
        .get('authProvider', this.authProvider.type)
        .getIcon()
    },
    getName() {
      return this.$registry
        .get('authProvider', this.authProvider.type)
        .getProviderName(this.authProvider)
    },
    openContext() {
      this.$refs.editMenuContext.toggle(
        this.$refs.editMenuContextLink,
        'bottom',
        'right'
      )
    },
    showUpdateSettingsModal() {
      this.$refs.editMenuContext.hide()
      this.$refs.updateSettingsModal.show()
    },
    showDeleteModal() {
      this.$refs.deleteModal.show()
      this.$refs.editMenuContext.hide()
    },
    onDeleteConfirmed() {
      this.$store.dispatch('authProviderAdmin/delete', this.authProvider)
      this.$refs.deleteModal.hide()
    },
    onSettingsUpdated() {
      this.$refs.updateSettingsModal.hide()
    },
    async setEnabled(enabled) {
      await this.$store.dispatch('authProviderAdmin/setEnabled', {
        authProvider: this.authProvider,
        enabled,
      })
    },
  },
}
</script>
