<template>
  <div>
    <a
      ref="contextLink"
      class="header__filter-link"
      :class="{ 'active active--primary': dashboard.public }"
      @click="context.toggle(contextLink, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon iconoir-link"></i>
      <span class="header__filter-name">
        {{ $t('shareDashboardLink.shareDashboard') }}
      </span>
    </a>

    <Context ref="context" max-height-if-outside-viewport>
      <div class="dashboard-sharing">
        <div v-if="!dashboard.public" class="dashboard-sharing__share-link">
          <div class="dashboard-sharing__share-link-title">
            {{ $t('shareDashboardLink.notSharedTitle') }}
          </div>
          <p class="dashboard-sharing__share-link-description">
            {{ $t('shareDashboardLink.notSharedText') }}
          </p>
          <Button
            type="secondary"
            icon="iconoir-link"
            :loading="loading"
            :disabled="loading"
            @click.stop="updateDashboard({ public: true })"
          >
            {{ $t('shareDashboardLink.createPrivateLink') }}
          </Button>
        </div>

        <template v-else>
          <div class="dashboard-sharing__shared-link">
            <div class="dashboard-sharing__shared-link-title">
              {{ $t('shareDashboardLink.sharedTitle') }}
            </div>
            <div class="dashboard-sharing__shared-link-description">
              {{ $t('shareDashboardLink.sharedDescription') }}
            </div>

            <div class="dashboard-sharing__shared-link-content">
              <div class="dashboard-sharing__shared-link-box">
                {{ shareUrl }}
              </div>
              <a
                v-tooltip="$t('shareDashboardLink.copyURL')"
                class="dashboard-sharing__shared-link-action"
                @click="copyShareUrlToClipboard()"
              >
                <i class="iconoir-copy" />
                <Copied ref="copied"></Copied>
              </a>
              <a
                v-tooltip="$t('shareDashboardLink.generateNewUrl')"
                class="dashboard-sharing__shared-link-action"
                @click.prevent="rotateSlugModal.show()"
              >
                <i class="iconoir-refresh-double" />
              </a>
            </div>

            <div class="dashboard-sharing__shared-link-options">
              <div class="dashboard-sharing__option">
                <SwitchInput
                  small
                  :value="dashboard.public_has_password"
                  @input="togglePassword"
                >
                  <i
                    class="switch__icon dashboard-sharing__option-icon"
                    :class="
                      dashboard.public_has_password
                        ? 'iconoir-lock'
                        : 'iconoir-globe'
                    "
                  />
                  <span>{{ $t(passwordOptionText) }}</span>
                </SwitchInput>
                <a
                  v-if="dashboard.public_has_password"
                  v-tooltip="$t('shareDashboardLink.changePassword')"
                  class="dashboard-sharing__option-change-password"
                  @click.stop="enablePasswordModal.show()"
                >
                  <i class="iconoir-edit-pencil" />
                </a>
                <!--
                  Kept inside the context so that clicks in the modals count as
                  clicks inside the context and don't close it.
                -->
                <DashboardEnablePasswordModal
                  ref="enablePasswordModal"
                  :dashboard="dashboard"
                />
                <DashboardDisablePasswordModal
                  ref="disablePasswordModal"
                  :dashboard="dashboard"
                />
              </div>

              <component
                :is="component"
                v-for="(component, i) in additionalShareLinkOptions"
                :key="i"
                :dashboard="dashboard"
                @update-dashboard="forceUpdateDashboard"
              />
            </div>
          </div>

          <div class="context__footer">
            <ButtonText
              icon="iconoir-cancel"
              @click.stop="updateDashboard({ public: false })"
            >
              {{ $t('shareDashboardLink.disableLink') }}
            </ButtonText>
          </div>
        </template>

        <!--
          Kept inside the context so that clicks in the modal count as clicks
          inside the context and don't close it.
        -->
        <DashboardRotateSlugModal
          ref="rotateSlugModal"
          :dashboard="dashboard"
        />
      </div>
    </Context>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useNuxtApp } from '#app'
import DashboardRotateSlugModal from '@baserow/modules/dashboard/components/sharing/DashboardRotateSlugModal'
import DashboardEnablePasswordModal from '@baserow/modules/dashboard/components/sharing/DashboardEnablePasswordModal'
import DashboardDisablePasswordModal from '@baserow/modules/dashboard/components/sharing/DashboardDisablePasswordModal'
import { updateDashboardSharing } from '@baserow/modules/dashboard/utils/sharing'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  dashboard: {
    type: Object,
    required: true,
  },
})

const { $store, $registry, $config, $router, $client } = useNuxtApp()

const context = ref(null)
const contextLink = ref(null)
const copied = ref(null)
const rotateSlugModal = ref(null)
const enablePasswordModal = ref(null)
const disablePasswordModal = ref(null)
const loading = ref(false)

const shareUrl = computed(() => {
  return (
    $config.public.baserowEmbeddedShareUrl +
    $router.resolve({
      name: 'dashboard-public',
      params: { slug: props.dashboard.slug },
    }).href
  )
})

const additionalShareLinkOptions = computed(() => {
  return Object.values($registry.getAll('plugin'))
    .flatMap((plugin) => plugin.getAdditionalDashboardShareLinkOptions())
    .filter((component) => component !== null)
})

const passwordOptionText = computed(() => {
  return props.dashboard.public_has_password
    ? 'shareDashboardLink.passwordProtected'
    : 'shareDashboardLink.restrictWithPassword'
})

/**
 * The switch itself never changes the password, the modals do after the
 * password was entered or the removal confirmed.
 */
const togglePassword = () => {
  if (props.dashboard.public_has_password) {
    disablePasswordModal.value.show()
  } else {
    enablePasswordModal.value.show()
  }
}

const copyShareUrlToClipboard = () => {
  copyToClipboard(shareUrl.value)
  copied.value.show()
}

/**
 * Creates or disables the link. Either change also removes a password, which
 * the helper reflects in the store from the response.
 */
const updateDashboard = async (values) => {
  const application = props.dashboard
  loading.value = true
  $store.dispatch('application/setItemLoading', { application, value: true })

  try {
    await updateDashboardSharing({ $client, $store }, application, values)
  } catch (error) {
    notifyIf(error, 'application')
  } finally {
    loading.value = false
    $store.dispatch('application/setItemLoading', { application, value: false })
  }
}

/**
 * Applies values that were already saved by another endpoint, like the premium
 * dashboard attributes, to the dashboard in the store.
 */
const forceUpdateDashboard = (data) => {
  $store.dispatch('application/forceUpdate', {
    application: props.dashboard,
    data,
  })
}
</script>
