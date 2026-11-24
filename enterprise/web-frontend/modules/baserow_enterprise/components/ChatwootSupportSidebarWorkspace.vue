<template>
  <li class="context__menu-item">
    <button
      type="button"
      class="context__menu-item-link"
      :class="{ 'context__menu-item-link--loading': loading }"
      :disabled="loading"
      @click="activate"
    >
      <i
        class="context__menu-item-icon"
        :class="deactivated ? 'iconoir-lock' : 'iconoir-chat-bubble-question'"
        aria-hidden="true"
      ></i>
      {{ $t('chatwootSupportSidebarWorkspace.directSupport') }}
    </button>
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      :workspace="workspace"
      initial-selected-type="support"
    ></PaidFeaturesModal>
  </li>
</template>

<script>
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

const CHATWOOT_BASE_URL = 'https://support.baserow.io'
const CHATWOOT_WIDGET_ID = 'chatwoot_live_chat_widget'
const CHATWOOT_TIMEOUT = 10_000

/**
 * The Chatwoot docs can be found here:
 * https://www.chatwoot.com/docs/product/channels/live-chat/sdk/setup
 */
export default {
  name: 'ChatwootSupportSidebarWorkspace',
  components: { PaidFeaturesModal },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['hide'],
  data() {
    return { loading: false }
  },
  computed: {
    deactivated() {
      return !this.$hasFeature(EnterpriseFeatures.SUPPORT, this.workspace.id)
    },
  },
  beforeUnmount() {
    this.stopLoading()
  },
  methods: {
    activate() {
      if (this.loading) {
        return
      }

      if (this.deactivated) {
        this.$refs.paidFeaturesModal.show()
      } else if (window.$chatwoot?.hasLoaded) {
        this.open()
      } else {
        this.load()
      }
      this.$emit('hide')
    },
    load() {
      this.loading = true
      window.addEventListener('chatwoot:ready', this.onReady)
      this._loadTimeout = window.setTimeout(this.onLoadError, CHATWOOT_TIMEOUT)

      if (window.$chatwoot) {
        // The SDK creates $chatwoot before the iframe is ready and skips a
        // second initialization. Reload the iframe to keep the conversation.
        const widget = document.getElementById(CHATWOOT_WIDGET_ID)
        if (widget) {
          widget.setAttribute('src', widget.src)
        } else {
          this.onLoadError()
        }
        return
      }

      window.chatwootSettings = {
        hideMessageBubble: true,
        position: 'right',
        useBrowserLanguage: false,
        type: 'standard',
        darkMode: 'light',
      }

      const script = document.createElement('script')
      this._sdkScript = script
      script.src = `${CHATWOOT_BASE_URL}/packs/js/sdk.js`
      script.async = true
      script.onload = () => {
        try {
          window.chatwootSDK.run({
            websiteToken: 'q4UGgPBqgB5RSEbzy3LbyGK8',
            baseUrl: CHATWOOT_BASE_URL,
          })
        } catch {
          this.onLoadError()
        }
      }
      script.onerror = this.onLoadError
      document.head.append(script)
    },
    stopLoading() {
      window.clearTimeout(this._loadTimeout)
      window.removeEventListener('chatwoot:ready', this.onReady)
      if (this._sdkScript) {
        this._sdkScript.onload = null
        this._sdkScript.onerror = null
        this._sdkScript.remove()
        this._sdkScript = null
      }
      this.loading = false
    },
    onLoadError() {
      this.stopLoading()
      this.$store.dispatch('toast/error', {
        title: this.$t('chatwootSupportSidebarWorkspace.loadError'),
      })
    },
    onReady() {
      if (!window.$chatwoot?.hasLoaded) {
        return
      }
      this.stopLoading()
      if (!this.deactivated) {
        this.open()
      }
    },
    open() {
      const userObject = this.$store.getters['auth/getUserObject']
      window.$chatwoot.setLocale(this.$i18n.locale)
      window.$chatwoot.setUser(`${window.location.hostname}-${userObject.id}`, {
        email: userObject.username,
        name: userObject.first_name,
      })
      window.$chatwoot.setCustomAttributes({
        workspaceId: this.workspace.id,
        userId: userObject.id,
        domain: window.location.hostname,
      })
      window.$chatwoot.toggle('open')
    },
  },
}
</script>
