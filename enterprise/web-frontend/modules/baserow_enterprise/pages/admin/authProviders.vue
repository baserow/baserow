<template>
  <div class="layout__col-2-scroll layout__col-2-scroll--white-background">
    <div class="auth-provider-admin">
      <div class="auth-provider-admin__header">
        <h2 class="auth-provider-admin__title">
          {{ $t('authProviders.title') }}
        </h2>
        <a ref="createContextLink" class="button" @click="showCreateContext()">
          {{ $t('authProviders.addProvider') }}
          <CreateAuthProviderContext
            ref="createContext"
            :auth-provider-types="authProviderTypesCanBeCreated"
            @create="showCreateModal($event)"
          />
          <CreateAuthProviderModal
            v-if="authProviderTypeToCreate"
            ref="createModal"
            :auth-provider-type="authProviderTypeToCreate"
            @created="$refs.createModal.hide()"
            @cancel="$refs.createModal.hide()"
          />
        </a>
      </div>
      <div v-if="authProviders.length > 0" class="auth-provider-admin__items">
        <component
          :is="getAdminListComponent(authProvider)"
          v-for="authProvider in authProviders"
          :key="authProvider.id"
          :auth-provider="authProvider"
        >
        </component>
      </div>
      <div v-else>
        <p>{{ $t('authProviders.noProviders') }}</p>
      </div>
      <div v-for="authProvider in authProviders" :key="authProvider.id"></div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import CreateAuthProviderContext from '@baserow_enterprise/components/admin/contexts/CreateAuthProviderContext.vue'
import CreateAuthProviderModal from '@baserow_enterprise/components/admin/modals/CreateAuthProviderModal.vue'

export default {
  components: { CreateAuthProviderContext, CreateAuthProviderModal },
  layout: 'app',
  middleware: 'staff',
  asyncData: async ({ store }) => {
    await store.dispatch('authProviderAdmin/fetchAll')
    await store.dispatch('authProviderAdmin/fetchNextProviderId')
  },
  data() {
    return {
      authProviderTypeToCreate: null,
    }
  },
  computed: {
    ...mapGetters({
      authProviderMap: 'authProviderAdmin/getAll',
      authProviders: 'authProviderAdmin/getAllOrdered',
    }),
    authProviderTypesCanBeCreated() {
      return Object.values(this.$registry.getAll('authProvider')).filter(
        (authProviderType) =>
          authProviderType.canCreateNew(this.authProviderMap)
      )
    },
  },
  methods: {
    getAdminListComponent(authProvider) {
      return this.$registry
        .get('authProvider', authProvider.type)
        .getAdminListComponent()
    },
    showCreateContext() {
      this.$refs.createContext.toggle(
        this.$refs.createContextLink,
        'bottom',
        'right',
        4
      )
    },
    async showCreateModal(authProviderType) {
      this.authProviderTypeToCreate = authProviderType
      // Wait for the modal to appear in DOM
      await this.$nextTick()
      this.$refs.createModal.show()
      this.$refs.createContext.hide()
    },
  },
}
</script>
