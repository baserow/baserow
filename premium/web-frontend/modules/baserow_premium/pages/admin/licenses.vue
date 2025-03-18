<template>
  <div class="layout__col-2-scroll layout__col-2-scroll--white-background">
    <div v-if="orderedLicenses.length === 0" class="placeholder">
      <div class="placeholder__icon">
        <i class="iconoir-shield-check"></i>
      </div>
      <h1 class="placeholder__title">
        {{ $t('licenses.titleNoLicenses') }}
      </h1>
      <p class="placeholder__content">
        {{ $t('licenses.noLicensesDescription') }}
      </p>
      <div class="licenses__features margin-bottom-2">
        <div
          v-for="licenseType in licenseTypesWithFeatureComponent"
          :key="licenseType.type"
        >
          <h2>{{ licenseType.getName() }}</h2>
          <component
            :is="licenseType.getFeaturesComponent()"
            class="margin-bottom-2"
          ></component>
        </div>
      </div>
      <div class="placeholder__action">
        <Button
          type="primary"
          size="large"
          icon="iconoir-plus"
          @click="$refs.registerModal.show()"
        >
          {{ $t('licenses.registerLicense') }}
        </Button>
        <RedirectToBaserowModal
          :href="'https://baserow.io/get-license/' + instanceId + '/'"
          target="_blank"
          >{{ $t('licenses.getLicense') }}</RedirectToBaserowModal
        >
      </div>
      <p>
        {{ $t('licenses.baserowInstanceId') }}
        <br />
        <span class="licenses__instance-id">{{ instanceId }}</span>
        <a
          class="licenses__instance-id-copy"
          @click.prevent="
            ;[copyToClipboard(instanceId), $refs.instanceIdCopied.show()]
          "
        >
          {{ $t('action.copy') }}
          <Copied ref="instanceIdCopied"></Copied>
        </a>
      </p>
    </div>
    <div v-else class="licenses">
      <div class="licenses__head">
        <h1 class="margin-bottom-0">
          {{ $t('licenses.titleLicenses') }}
        </h1>
        <div>
          <Button
            type="primary"
            icon="iconoir-plus"
            @click="$refs.registerModal.show()"
          >
            {{ $t('licenses.registerLicense') }}
          </Button>
          <RedirectToBaserowModal
            :href="'https://baserow.io/get-license/' + instanceId + '/'"
            target="_blank"
            size="regular"
            >{{ $t('licenses.getLicense') }}</RedirectToBaserowModal
          >
        </div>
      </div>
      <div class="margin-bottom-3">
        {{ $t('licenses.baserowInstanceId') }}
        <span class="licenses__instance-id">{{ instanceId }}</span>
        <a
          class="licenses__instance-id-copy"
          @click.prevent="
            ;[copyToClipboard(instanceId), $refs.instanceIdCopied.show()]
          "
        >
          {{ $t('action.copy') }}
          <Copied ref="instanceIdCopied"></Copied>
        </a>
      </div>
      <div class="licenses__items">
        <nuxt-link
          v-for="license in orderedLicenses"
          :key="license.id"
          :to="{ name: 'admin-license', params: { id: license.id } }"
          class="licenses__item"
        >
          <span class="licenses__item-icon-hover">
            <i class="iconoir-arrow-right"></i>
          </span>
          <div class="licenses__item-head">
            <div class="licenses__item-title">
              {{ $t('licenses.licenceId') }}
              <span class="licenses__item-title-license">{{
                license.license_id
              }}</span>
            </div>
            <Badge
              :color="getLicenseType(license).getLicenseBadgeColor()"
              bold
              class="margin-right-1"
            >
              {{ getLicenseType(license).getName() }}</Badge
            >
            <Badge v-if="!license.is_active" color="red">{{
              $t('licenses.expired')
            }}</Badge>
          </div>
          <div class="licenses__item-validity">
            {{
              $t('licenses.validity', {
                start: localDate(license.valid_from),
                end: localDate(license.valid_through),
              })
            }}
          </div>
          <ul class="licenses__item-details">
            <li class="licenses__item-detail-item">
              {{ license.seats_taken }} / {{ license.seats }}
              {{ $t('licenses.seats') }}
            </li>
            <li
              v-if="license.application_users"
              class="licenses__item-detail-item"
            >
              {{ license.application_users_taken }} /
              {{ license.application_users }}
              {{ $t('licenses.applicationUsers') }}
            </li>
          </ul>
          <ul class="licenses__item-details">
            <li
              class="licenses__item-detail-item"
              v-for="(feature, index) in licenseFeatureDescription(license)"
              :key="index"
            >
              {{ feature.name }}
              <i
                class="iconoir-check licenses__item-detail-item-icon"
                :class="{
                  'iconoir-check license-yes': feature.enabled,
                  'iconoir-cancel license-no': !feature.enabled,
                }"
              ></i>
            </li>
          </ul>
        </nuxt-link>
      </div>
    </div>
    <RegisterLicenseModal ref="registerModal"></RegisterLicenseModal>
  </div>
</template>

<script>
import LicenseService from '@baserow_premium/services/license'
import RegisterLicenseModal from '@baserow_premium/components/license/RegisterLicenseModal'
import RedirectToBaserowModal from '@baserow_premium/components/RedirectToBaserowModal'
import PremiumFeatures from '@baserow_premium/components/PremiumFeatures'
import EnterpriseFeatures from '@baserow_enterprise/components/EnterpriseFeatures'
import moment from '@baserow/modules/core/moment'
import SettingsService from '@baserow/modules/core/services/settings'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  components: {
    RedirectToBaserowModal,
    RegisterLicenseModal,
    PremiumFeatures,
    EnterpriseFeatures,
  },
  layout: 'app',
  middleware: 'staff',
  async asyncData({ app, error }) {
    try {
      const { data: instanceData } = await SettingsService(
        app.$client
      ).getInstanceID()
      const { data } = await LicenseService(app.$client).fetchAll()
      return {
        licenses: data,
        instanceId: instanceData.instance_id,
      }
    } catch {
      return error({
        statusCode: 400,
        message: 'Something went wrong while fetching the licenses.',
      })
    }
  },
  computed: {
    orderedLicenses() {
      return this.licenses
        .slice()
        .sort(
          (a, b) =>
            new Date(a.valid_from).getTime() - new Date(b.valid_from).getTime()
        )
        .sort((a, b) =>
          a.is_active === b.is_active ? 0 : a.is_active ? -1 : 1
        )
        .sort((a, b) => a.application_users - b.application_users)
    },
    licenseTypesWithFeatureComponent() {
      return Object.values(this.$registry.getAll('license')).filter(
        (licenseType) => licenseType.getFeaturesComponent() !== null
      )
    },
  },
  methods: {
    localDate(date) {
      return moment.utc(date).local().format('ll')
    },
    copyToClipboard(value) {
      copyToClipboard(value)
    },
    getLicenseType(license) {
      return this.$registry.get('license', license.product_code)
    },
    licenseFeatureDescription(license) {
      return this.getLicenseType(license).getFeaturesDescription()
    },
  },
}
</script>
