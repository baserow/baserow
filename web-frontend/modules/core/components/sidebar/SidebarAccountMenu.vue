<template>
  <Context
    ref="context"
    class="sidebar-account-menu"
    max-height-if-outside-viewport
    overflow-scroll
    @shown="onShow"
    @hidden="onHidden"
    @keydown.esc="onEscape"
  >
    <div class="sidebar__user">
      <div class="sidebar__user-email">{{ email }}</div>

      <ul class="context__menu">
        <li class="context__menu-item">
          <button
            ref="settingsTrigger"
            type="button"
            class="context__menu-item-link"
            @click="settingsModal.show()"
          >
            <i class="context__menu-item-icon iconoir-user-circle"></i>
            {{ $t('sidebar.settings') }}
          </button>
          <SettingsModal ref="settingsModal"></SettingsModal>
        </li>

        <component
          :is="component"
          v-for="(component, index) in accountComponents"
          :key="'sidebarUserContextComponent' + index"
          @hide="context.hide()"
        ></component>

        <li v-if="isStaff" class="context__menu-item">
          <button
            ref="adminTrigger"
            type="button"
            class="context__menu-item-link"
            :aria-expanded="adminMenuOpen"
            @click="toggleAdminMenu"
          >
            <i class="context__menu-item-icon iconoir-settings"></i>
            {{ $t('sidebar.adminTools') }}
            <i
              class="sidebar-account-menu__chevron iconoir-nav-arrow-right"
              aria-hidden="true"
            ></i>
          </button>
        </li>

        <li v-if="anyGuidedTourActive" class="context__menu-item">
          <button
            type="button"
            class="context__menu-item-link"
            @click="replayGuidedTour()"
          >
            <i class="context__menu-item-icon iconoir-help-circle"></i>
            {{ $t('sidebar.replayGuidedTour') }}
          </button>
        </li>

        <li class="context__menu-item context__menu-item--with-separator">
          <button
            type="button"
            class="context__menu-item-link"
            :class="{ 'context__menu-item-link--loading': logoffLoading }"
            @click="logoff()"
          >
            <i class="context__menu-item-icon iconoir-log-out"></i>
            {{ $t('sidebar.logoff') }}
          </button>
        </li>
      </ul>
      <Context
        v-if="isStaff"
        ref="adminContext"
        class="sidebar-admin-menu"
        :horizontal-viewport-margin="8"
        max-height-if-outside-viewport
        overflow-scroll
        @shown="onAdminMenuShown"
        @hidden="adminMenuOpen = false"
        @keydown.esc.stop.prevent="closeAdminMenu"
      >
        <SidebarAdmin show-section-separators @activate="onAdminActivate" />
      </Context>
    </div>
  </Context>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, useRoute, useRouter } from '#imports'

import SidebarAdmin from '@baserow/modules/core/components/sidebar/SidebarAdmin.vue'
import SettingsModal from '@baserow/modules/core/components/settings/SettingsModal.vue'
import { logoutAndRedirectToLogin } from '@baserow/modules/core/utils/auth'

const props = defineProps({
  selectedWorkspace: {
    type: Object,
    required: true,
  },
})
const emit = defineEmits(['hidden', 'shown', 'toggle-admin'])

const store = useStore()
const { $registry } = useNuxtApp()
const route = useRoute()
const router = useRouter()

const context = ref(null)
const adminContext = ref(null)
const adminTrigger = ref(null)
const settingsTrigger = ref(null)
const settingsModal = ref(null)
const adminMenuOpen = ref(false)
const logoffLoading = ref(false)

const email = computed(() => store.getters['auth/getUsername'])
const isStaff = computed(() => store.getters['auth/isStaff'])
const accountComponents = computed(() =>
  Object.values($registry.getAll('plugin'))
    .flatMap((plugin) =>
      plugin.getUserContextComponents(props.selectedWorkspace)
    )
    .filter((component) => component !== null)
)
const anyGuidedTourActive = computed(() =>
  Object.values($registry.getAll('guidedTour')).some((tour) =>
    tour.isActive(route)
  )
)

async function onShow() {
  emit('shown')
  await nextTick()
  if (context.value?.isOpen()) {
    settingsTrigger.value?.focus()
  }
}

function onHidden() {
  if (adminContext.value?.isOpen()) {
    adminContext.value.hide()
  }
  emit('hidden')
}

function onEscape(event) {
  if (!event.defaultPrevented) {
    event.preventDefault()
    event.stopPropagation()

    const opener = context.value.opener
    context.value.hide()
    opener?.focus()
  }
}

function toggleAdminMenu(event) {
  const trigger = event.currentTarget
  adminContext.value.toggle(
    trigger,
    'over-top',
    'left',
    0,
    trigger.offsetWidth + 12
  )
}

async function onAdminMenuShown() {
  if (!context.value?.isOpen() || !adminContext.value?.isOpen()) {
    return
  }
  adminMenuOpen.value = true
  await nextTick()
  if (adminMenuOpen.value) {
    adminContext.value
      ?.getTeleportedElement()
      ?.querySelector('a[href]')
      ?.focus()
  }
}

function closeAdminMenu() {
  adminContext.value.hide()
  adminTrigger.value?.focus()
}

function onAdminActivate() {
  context.value.hide()
  emit('toggle-admin', true)
}

async function replayGuidedTour() {
  context.value.hide()
  await nextTick()
  await store.dispatch('guidedTour/forceStart')
}

async function logoff() {
  logoffLoading.value = true
  await logoutAndRedirectToLogin(router, store, false, false, true)
}

defineExpose({ toggle: (...args) => context.value.toggle(...args) })
</script>
