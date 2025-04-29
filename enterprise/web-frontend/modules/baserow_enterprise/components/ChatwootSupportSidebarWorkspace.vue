<template>
  <li
    class="tree__item"
    :class="{
      'tree__item--loading': loading,
      'tree__action--deactivated': deactivated,
    }"
  >
    <div class="tree__action">
      <a
        v-if="deactivated"
        href="#"
        class="tree__link"
        @click.prevent="$refs.paidFeaturesModal.show()"
      >
        <i class="tree__icon iconoir-lock"></i>
        <span class="tree__link-text">{{
          $t('chatwootSupportSidebarWorkspace.directSupport')
        }}</span>
      </a>
      <a v-else class="tree__link" @click="open">
        <i class="tree__icon iconoir-chat-bubble-question"></i>
        <span class="tree__link-text">{{
          $t('chatwootSupportSidebarWorkspace.directSupport')
        }}</span>
      </a>
    </div>
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
  data() {
    return {
      ready: false,
      loading: false,
    }
  },
  computed: {
    deactivated() {
      return !this.$hasFeature(EnterpriseFeatures.SUPPORT, this.workspace.id)
    },
  },
  mounted() {
    // It could be that chatwoot is ready. In that case, $chatwoot should be set on the
    // window object.
    this.ready = Object.prototype.hasOwnProperty.call(window, '$chatwoot')
    window.addEventListener('chatwoot:ready', this.onReady)
  },
  beforeDestroy() {
    window.removeEventListener('chatwoot:ready', this.onReady)
  },
  methods: {
    load() {
      this.loading = true
      window.chatwootSettings = {
        hideMessageBubble: true,
        position: 'right',
        useBrowserLanguage: false,
        type: 'standard',
        darkMode: 'light',
      }

      const BASE_URL = 'https://support.baserow.io'
      const g = document.createElement('script')
      const s = document.getElementsByTagName('script')[0]
      g.src = BASE_URL + '/packs/js/sdk.js'
      g.defer = true
      g.async = true
      s.parentNode.insertBefore(g, s)
      g.onload = function () {
        window.chatwootSDK.run({
          websiteToken: 'q4UGgPBqgB5RSEbzy3LbyGK8',
          baseUrl: BASE_URL,
        })
      }
    },
    onReady() {
      this.ready = true
      this.loading = false
      this.open()
    },
    open() {
      if (!this.ready) {
        this.load()
      }

      if (!this.ready || this.loading) {
        return
      }

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
