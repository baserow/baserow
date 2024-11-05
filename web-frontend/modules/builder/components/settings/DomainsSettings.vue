<template>
  <div v-if="!showCreationForm" class="domains-settings">
    <Error :error="error"></Error>

    <div
      v-if="$fetchState.pending && !error.visible"
      class="domains-settings__loading"
    >
      <span class="loading loading-absolute-center"></span>
    </div>

    <template v-else>
      <DomainCard
        v-for="domain in domains"
        :key="domain.id"
        class="margin-bottom-2"
        :domain="domain"
        :is-only-domain="domains.length === 1"
        @delete="deleteDomain(domain)"
      />
    </template>
    <p v-if="!error.visible && !$fetchState.pending && domains.length === 0">
      {{ $t('domainSettings.noDomainMessage') }}
    </p>
  </div>
  <DomainForm
    v-else
    ref="form"
    :builder="builder"
    :hide-form="hideForm"
    @loading="$emit('domain-form-loading', $event)"
  />
</template>

<script>
import { mapActions, mapGetters } from 'vuex'
import error from '@baserow/modules/core/mixins/error'
import DomainCard from '@baserow/modules/builder/components/domain/DomainCard'
import DomainForm from '@baserow/modules/builder/components/domain/DomainForm'
import DomainsSettingsFooter from '@baserow/modules/builder/components/settings/DomainsSettingsFooter.vue'

export default {
  name: 'DomainsSettings',
  components: { DomainCard, DomainForm },
  mixins: [error],
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      showCreationForm: false,
    }
  },
  async fetch() {
    try {
      await this.actionFetchDomains({ builderId: this.builder.id })
      this.hideError()
    } catch (error) {
      this.handleError(error)
    }
  },
  computed: {
    ...mapGetters({ domains: 'domain/getDomains' }),
  },
  methods: {
    ...mapActions({
      actionDeleteDomain: 'domain/delete',
      actionFetchDomains: 'domain/fetch',
    }),
    hideForm() {
      this.showCreationForm = false
      this.hideError()
    },
    async deleteDomain({ id }) {
      try {
        await this.actionDeleteDomain({ domainId: id })
      } catch (error) {
        this.handleError(error)
      }
    },
    getTitle() {
      return this.$t('domainSettings.titleOverview')
    },
    getFooterComponent() {
      return DomainsSettingsFooter
    },
    showForm() {
      this.showCreationForm = true
    },
    submitForm() {
      this.$refs.form.submitForm()
    },
  },
}
</script>
