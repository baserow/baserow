import debounce from 'lodash/debounce'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { AgentContextMixin } from '@baserow_enterprise/composables/useAgentContext'

/**
 * Shared by the channel card components: the props the section hands them
 * and a debounced way to save part of the channel's config.
 */
export default {
  mixins: [AgentContextMixin],
  props: {
    channel: {
      type: Object,
      required: true,
    },
    application: {
      type: Object,
      required: true,
    },
    /**
     * The editable local copy seeded by the channel type; the card writes
     * into it and saves from it.
     */
    draft: {
      type: Object,
      required: true,
    },
    canUpdate: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  created() {
    this.debouncedConfigSave = debounce(() => this.saveConfig(), 1000)
  },
  beforeUnmount() {
    this.debouncedConfigSave.flush()
  },
  computed: {
    agentName() {
      return (
        this.$store.getters[`${this.storePrefix}agentApplication/getAgent`]
          ?.name || this.application.name
      )
    },
  },
  methods: {
    async updateChannel(values) {
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateChannel`,
          { channelId: this.channel.id, values }
        )
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    /**
     * The config values the draft holds; a card overrides it and calls
     * `onConfigChanged` from its inputs.
     */
    draftConfigValues() {
      return {}
    },
    onConfigChanged() {
      if (this.canUpdate) {
        this.debouncedConfigSave()
      }
    },
    async saveConfig() {
      const values = this.draftConfigValues()
      const unchanged = Object.entries(values).every(([key, value]) =>
        Array.isArray(value)
          ? JSON.stringify(value) ===
            JSON.stringify(this.channel.config?.[key] || [])
          : value === (this.channel.config?.[key] ?? '')
      )
      if (!unchanged) {
        await this.updateChannel({ config: values })
      }
    },
  },
}
