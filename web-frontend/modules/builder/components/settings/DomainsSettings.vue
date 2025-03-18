<template>
  <div v-if="!showForm">
    <h2 class="box__title">{{ $t('domainSettings.titleOverview') }}</h2>
    <Error :error="error"></Error>
    <div class="actions actions--right">
      <Button icon="iconoir-plus" @click="showForm = true">
        {{ $t('domainSettings.addDomain') }}
      </Button>
    </div>
    <div
      v-if="$fetchState.pending && !error.visible"
      class="loading domains-settings__loading"
    />
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
    <p
      v-if="!error.visible && !$fetchState.pending && domains.length === 0"
      class="margin-top-3"
    >
      {{ $t('domainSettings.noDomainMessage') }}
    </p>
  </div>
  <DomainForm
    v-else
    :builder="builder"
    :hide-form="hideForm"
    @created="hideModalIfRequired"
  />
</template>

<script>
import { mapActions, mapGetters } from 'vuex'
import error from '@baserow/modules/core/mixins/error'
import DomainCard from '@baserow/modules/builder/components/domain/DomainCard'
import DomainForm from '@baserow/modules/builder/components/domain/DomainForm'
import builderSetting from '@baserow/modules/builder/components/settings/mixins/builderSetting'

export default {
  name: 'DomainsSettings',
  components: { DomainCard, DomainForm },
  mixins: [error, builderSetting],
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
      this.showForm = false
      this.hideError()
    },
    async deleteDomain({ id }) {
      try {
        await this.actionDeleteDomain({ domainId: id })
      } catch (error) {
        this.handleError(error)
      }
    },
  },
}
</script>
