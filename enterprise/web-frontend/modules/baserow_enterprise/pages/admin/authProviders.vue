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
            @created="createModal?.hide()"
            @cancel="createModal?.hide()"
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

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, definePageMeta, useI18n, useHead } from '#imports'
import CreateAuthProviderContext from '@baserow_enterprise/components/admin/contexts/CreateAuthProviderContext.vue'
import CreateAuthProviderModal from '@baserow_enterprise/components/admin/modals/CreateAuthProviderModal.vue'

// Page meta
definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

// Composables
const store = useStore()
const { $registry } = useNuxtApp()
const { t: $t } = useI18n()

useHead({ title: $t('authProviders.title') })

// Template refs
const createContextLink = ref(null)
const createContext = ref(null)
const createModal = ref(null)

// Reactive state
const authProviderTypeToCreate = ref(null)

// Fetch data on page load
await store.dispatch('authProviderAdmin/fetchAll')
await store.dispatch('authProviderAdmin/fetchNextProviderId')

// Computed
const authProviderMap = computed(
  () => store.getters['authProviderAdmin/getAll']
)
const authProviders = computed(
  () => store.getters['authProviderAdmin/getAllOrdered']
)

const authProviderTypesCanBeCreated = computed(() => {
  return Object.values($registry.getAll('authProvider')).filter(
    (authProviderType) => authProviderType.canCreateNew(authProviderMap.value)
  )
})

// Methods
function getAdminListComponent(authProvider) {
  return $registry
    .get('authProvider', authProvider.type)
    .getAdminListComponent()
}

function showCreateContext() {
  createContext.value?.toggle(createContextLink.value, 'bottom', 'right', 4)
}

async function showCreateModal(authProviderType) {
  authProviderTypeToCreate.value = authProviderType
  // Wait for the modal to appear in DOM
  await nextTick()
  createModal.value?.show()
  createContext.value?.hide()
}
</script>
