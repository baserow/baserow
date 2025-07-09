<template>
  <Modal @show="onShow()">
    <h2 class="box__title">
      {{ $t('publishActionModal.title') }}
    </h2>
    <Error :error="error"></Error>

    <template v-if="!hasVisibleError">
      <template v-if="domains.length">
        <p>{{ $t('publishActionModal.description') }}</p>

        <div
          v-for="(domain, index) in domains"
          :key="domain.id"
          class="publish-action-modal__container"
        >
          <Radio v-model="selectedDomainId" :value="domain.id">
            <span class="publish-action-modal__domain-name">{{
              domain.domain_name
            }}</span>
            <a
              v-if="domain.last_published"
              v-tooltip="$t('action.copyToClipboard')"
              class="publish-action-modal__copy-domain"
              tooltip-position="top"
              @click.stop="
                ;[copyDomainUrl(domain), $refs.domainCopied[index].show()]
              "
            >
              <i class="iconoir-copy" />
              <Copied ref="domainCopied" />
            </a>
            <a
              v-if="domain.last_published"
              v-tooltip="$t('publishActionModal.openInNewTab')"
              tooltip-position="top"
              class="publish-action-modal__domain-link"
              :href="getDomainUrl(domain)"
              target="_blank"
              @click.stop=""
            >
              <i class="iconoir-open-new-window" />
            </a>
          </Radio>
          <LastPublishedDomainDate
            :domain="domain"
            class="publish-action-modal__last-update"
          />
        </div>
      </template>
      <div v-else-if="fetchingDomains" class="loading-spinner"></div>
      <p v-else>{{ $t('publishActionModal.noDomain') }}</p>
    </template>

    <Alert v-if="jobHasSucceeded" type="success">
      <template #title>{{
        $t('publishActionModal.publishSucceedTitle')
      }}</template>
      <p>{{ $t('publishActionModal.publishSucceedDescription') }}</p>
      <template #actions>
        <Button tag="a" :href="getDomainUrl(selectedDomain)" target="_blank">{{
          $t('publishActionModal.publishSucceedLink')
        }}</Button>
      </template>
    </Alert>

    <div class="modal-progress__actions">
      <ProgressBar
        v-if="jobIsRunning"
        :value="job.progress_percentage"
        :status="jobHumanReadableState"
      />
      <div class="align-right">
        <Button
          v-if="domains.length"
          size="large"
          :loading="jobIsRunning || loading"
          :disabled="loading || jobIsRunning || !selectedDomainId"
          @click="publishSite()"
        >
          {{ $t('publishActionModal.publish') }}
        </Button>
        <template v-else-if="!fetchingDomains">
          <Button tag="a" @click="openDomainSettings">
            {{ $t('publishActionModal.addDomain') }}
          </Button>
        </template>
        <BuilderSettingsModal
          ref="domainSettingsModal"
          hide-after-create
          :builder="builder"
          :workspace="workspace"
        />
      </div>
    </div>
  </Modal>
</template>

<script>
import { mapActions, mapGetters } from 'vuex'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'
import PublishedDomainService from '@baserow/modules/builder/services/publishedBuilder'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import LastPublishedDomainDate from '@baserow/modules/builder/components/domain/LastPublishedDomainDate'
import BuilderSettingsModal from '@baserow/modules/builder/components/settings/BuilderSettingsModal'
import { DomainsBuilderSettingsType } from '@baserow/modules/builder/builderSettingTypes'

export default {
  name: 'PublishActionModal',
  components: { BuilderSettingsModal, LastPublishedDomainDate },
  mixins: [modal, error, jobProgress],
  inject: ['workspace'],
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  data() {
    return { selectedDomainId: null, loading: false, fetchingDomains: false }
  },
  computed: {
    ...mapGetters({ domains: 'domain/getDomains' }),
    selectedDomain() {
      return this.domains.find((domain) => domain.id === this.selectedDomainId)
    },
  },
  watch: {
    selectedDomainId() {
      this.job = null
    },
    domains() {
      if (!this.selectedDomainId) {
        this.selectedDomainId = this.domains.length ? this.domains[0].id : null
      }
    },
  },
  beforeDestroy() {
    this.stopPollIfRunning()
  },
  methods: {
    ...mapActions({
      actionFetchDomains: 'domain/fetch',
      actionForceUpdateDomain: 'domain/forceUpdate',
    }),
    async onShow() {
      this.hideError()
      this.job = null
      this.loading = false
      this.selectedDomainId = null
      this.fetchingDomains = true
      try {
        await this.actionFetchDomains({ builderId: this.builder.id })
        this.hideError()
      } catch (error) {
        this.handleError(error)
      } finally {
        this.fetchingDomains = false
      }
    },
    async publishSite() {
      this.loading = true
      this.hideError()
      try {
        const { data: job } = await PublishedDomainService(
          this.$client
        ).publish({
          id: this.selectedDomainId,
        })
        this.startJobPoller(job)
      } catch (error) {
        notifyIf(error)
      } finally {
        this.fetchingDomains = false
        this.loading = false
      }
    },
    onJobFailed() {
      this.showError(
        this.$t('publishActionModal.publishFailedTitle'),
        this.$t('publishActionModal.publishFailedDescription')
      )
      this.loading = false
    },
    onJobDone() {
      this.actionForceUpdateDomain({
        domainId: this.selectedDomainId,
        values: { last_published: new Date() },
      })
      this.loading = false
    },
    onJobPollingError(error) {
      notifyIf(error)
      this.loading = false
    },
    getDomainUrl(domain) {
      const url = new URL(this.$config.PUBLIC_WEB_FRONTEND_URL)
      return `${url.protocol}//${domain.domain_name}${
        url.port ? `:${url.port}` : ''
      }`
    },
    copyDomainUrl(domain) {
      copyToClipboard(this.getDomainUrl(domain))
    },
    getCustomHumanReadableJobState(state) {
      if (state === 'importing') {
        return this.$t('publishActionModal.importingState')
      }
      return ''
    },
    openDomainSettings() {
      // Open the builder settings modal, which is instructed to select the domain
      // settings instance first, and pass `DomainsBuilderSettingsType.getType()` into
      // `show` so that the create domain form is immediately presented.
      this.$refs.domainSettingsModal.show(
        DomainsBuilderSettingsType.getType(),
        true
      )
    },
  },
}
</script>
