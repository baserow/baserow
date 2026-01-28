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
        <div v-for="(features, planName) in paidFeaturePlans" :key="planName">
          <h2>{{ planName }}</h2>
          <ul class="premium-features margin-bottom-2">
            <li
              v-for="feature in features"
              :key="feature"
              class="premium-features__feature"
            >
              <i class="iconoir-check premium-features__feature-icon"></i>
              {{ feature.getName() }}
            </li>
          </ul>
        </div>
      </div>
      <div class="placeholder__action">
        <Button
          type="primary"
          size="large"
          icon="iconoir-plus"
          @click="showRegisterModal"
        >
          {{ $t('licenses.registerLicense') }}
        </Button>
        <RedirectToBaserowModal :href="getLicenseURL" target="_blank">
          {{ $t('licenses.getLicense') }}
        </RedirectToBaserowModal>
      </div>
      <p>
        {{ $t('licenses.baserowInstanceId') }}
        <br />
        <span class="licenses__instance-id">{{ instanceId }}</span>
        <a class="licenses__instance-id-copy" @click.prevent="onCopyInstanceId">
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
          <Button type="primary" icon="iconoir-plus" @click="showRegisterModal">
            {{ $t('licenses.registerLicense') }}
          </Button>
          <RedirectToBaserowModal
            :href="getLicenseURL"
            target="_blank"
            size="regular"
          >
            {{ $t('licenses.getLicense') }}
          </RedirectToBaserowModal>
        </div>
      </div>
      <div class="margin-bottom-3">
        {{ $t('licenses.baserowInstanceId') }}
        <span class="licenses__instance-id">{{ instanceId }}</span>
        <a class="licenses__instance-id-copy" @click.prevent="onCopyInstanceId">
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
              <span class="licenses__item-title-license">
                {{ license.license_id }}
              </span>
            </div>
            <Badge
              :color="getLicenseType(license).getLicenseBadgeColor()"
              bold
              class="margin-right-1"
            >
              {{ getLicenseType(license).getName() }}
            </Badge>
            <Badge v-if="!license.is_active" color="red">
              {{ $t('licenses.expired') }}
            </Badge>
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
              v-for="(feature, index) in licenseFeatureDescription(license)"
              :key="index"
              class="licenses__item-detail-item"
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
    <RegisterLicenseModal
      ref="registerModal"
      :instance-id="instanceId"
    ></RegisterLicenseModal>
  </div>
</template>

<script setup>
import LicenseService from '@baserow_premium/services/license'
import RegisterLicenseModal from '@baserow_premium/components/license/RegisterLicenseModal'
import RedirectToBaserowModal from '@baserow_premium/components/RedirectToBaserowModal'
import moment from '@baserow/modules/core/moment'
import SettingsService from '@baserow/modules/core/services/settings'
import { copyToClipboard as copyToClipboardUtil } from '@baserow/modules/database/utils/clipboard'
import { getPricingURL } from '@baserow_premium/utils/pricing'

definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

const { $client, $registry, $i18n } = useNuxtApp()

useHead({ title: $i18n.t('licenses.titleLicenses') })

// Fetch data using useAsyncData and return the values from the callback
const { data } = await useAsyncData('licensesPage', async () => {
  try {
    const [{ data: instanceData }, { data: licensesData }] = await Promise.all([
      SettingsService($client).getInstanceID(),
      LicenseService($client).fetchAll(),
    ])

    return {
      licenses: licensesData,
      instanceId: instanceData.instance_id,
    }
  } catch (e) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Something went wrong while fetching the licenses.',
    })
  }
})

const licenses = computed(() => data.value?.licenses || [])
const instanceId = computed(() => data.value?.instanceId || '')

const getLicenseURL = computed(() => getPricingURL(instanceId.value))

const paidFeaturePlans = computed(() => {
  const plans = {}
  Object.values($registry.getAll('paidFeature')).forEach((feature) => {
    const plan = feature.getPlan()
    if (!Object.prototype.hasOwnProperty.call(plans, plan)) {
      plans[plan] = []
    }
    plans[plan].push(feature)
  })
  return plans
})

const orderedLicenses = computed(() => {
  return licenses.value
    .slice()
    .sort(
      (a, b) =>
        new Date(a.valid_from).getTime() - new Date(b.valid_from).getTime()
    )
    .sort((a, b) => (a.is_active === b.is_active ? 0 : a.is_active ? -1 : 1))
    .sort((a, b) => a.application_users - b.application_users)
})

function localDate(date) {
  return moment.utc(date).local().format('ll')
}

function getLicenseType(license) {
  return $registry.get('license', license.product_code)
}

function licenseFeatureDescription(license) {
  return getLicenseType(license).getFeaturesDescription()
}

// Template refs for modals / copied indicator
const registerModal = ref(null)
const instanceIdCopied = ref(null)

function showRegisterModal() {
  if (registerModal.value && typeof registerModal.value.show === 'function') {
    registerModal.value.show()
  }
}

function onCopyInstanceId() {
  if (!instanceId.value) return
  copyToClipboardUtil(instanceId.value)
  if (
    instanceIdCopied.value &&
    typeof instanceIdCopied.value.show === 'function'
  ) {
    instanceIdCopied.value.show()
  }
}
</script>
