<template>
  <div class="layout__col-2-scroll layout__col-2-scroll--white-background">
    <div v-if="license" class="license-detail">
      <h1>
        {{ $t('license.title', { name: licenseType.getName() }) }}
      </h1>
      <div class="license-detail__users">
        <h2>{{ $t('license.users') }}</h2>
        <ManualLicenseSeatsForm
          v-if="licenseType.getSeatsManuallyAssigned()"
          :license="license"
        ></ManualLicenseSeatsForm>
        <AutomaticLicenseSeats
          v-else
          :license="license"
        ></AutomaticLicenseSeats>
      </div>
      <div class="license-detail__body">
        <div class="license-detail__body-left">
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.licenseId') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ license.license_id }}
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.plan') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              <Badge :color="licenseType.getLicenseBadgeColor()" bold>
                {{ licenseType.getName() }}
              </Badge>
              <Badge v-if="!license.is_active" color="red"
                >{{ $t('licenses.expired') }}
              </Badge>
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.validFrom') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ localDateTime(license.valid_from) }}
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.validThrough') }}
              </div>
              <div class="license-detail__item-description">
                {{ $t('license.validThroughDescription') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ localDateTime(license.valid_through) }}
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.lastCheck') }}
              </div>
              <div class="license-detail__item-description">
                {{ $t('license.lastCheckDescription') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              <div v-if="checkLoading" class="loading"></div>
              <template v-else>
                {{ localDateTime(license.last_check) }}
                <a @click="check()">{{ $t('license.checkNow') }}</a>
              </template>
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.seats') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ license.seats_taken }} / {{ license.seats }}
            </div>
          </div>

          <div v-if="license.application_users" class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.applicationUsers') }}
              </div>
              <div class="license-detail__item-description">
                {{ $t('license.applicationUsersDescription') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ license.application_users_taken }} /
              {{ license.application_users }}
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.licensedTo') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ license.issued_to_name }} ({{ license.issued_to_email }})
            </div>
          </div>
          <div
            v-for="(feature, index) in licenseFeatureDescription"
            :key="index"
            class="license-detail__item"
          >
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ feature.name }}
              </div>
            </div>
            <div class="license-detail__item-value">
              <i
                class="iconoir-check"
                :class="{
                  'iconoir-check license-yes': feature.enabled,
                  'iconoir-cancel license-no': !feature.enabled,
                }"
              ></i>
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.applications') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ $t('license.unlimited') }}
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.rowUsage') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ $t('license.unlimited') }}
            </div>
          </div>
          <div class="license-detail__item">
            <div class="license-detail__item-label">
              <div class="license-detail__item-name">
                {{ $t('license.storeUsage') }}
              </div>
            </div>
            <div class="license-detail__item-value">
              {{ $t('license.unlimited') }}
            </div>
          </div>
        </div>
        <div class="license-detail__body-right">
          <div class="delete-section">
            <div class="delete-section__label">
              <div class="delete-section__label-icon">
                <i class="iconoir-warning-triangle"></i>
              </div>
              {{ $t('license.disconnectLicense') }}
            </div>
            <i18n-t keypath="license.disconnectDescription" tag="p">
              <template #contact>
                <a href="https://baserow.io/contact" target="_blank"
                  >baserow.io/contact</a
                >
              </template>
            </i18n-t>

            <Button type="danger" @click="disconnectModal?.show()">
              {{ $t('license.disconnectLicense') }}
            </Button>
            <DisconnectLicenseModal
              ref="disconnectModal"
              :license="license"
            ></DisconnectLicenseModal>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import moment from '@baserow/modules/core/moment'
import { notifyIf } from '@baserow/modules/core/utils/error'
import LicenseService from '@baserow_premium/services/license'
import DisconnectLicenseModal from '@baserow_premium/components/license/DisconnectLicenseModal'
import ManualLicenseSeatsForm from '@baserow_premium/components/license/ManualLicenseSeatForm'
import AutomaticLicenseSeats from '@baserow_premium/components/license/AutomaticLicenseSeats'

definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

const route = useRoute()
const router = useRouter()
const { $client, $registry } = useNuxtApp()

// Fetch license data
const { data } = await useAsyncData(`license-${route.params.id}`, async () => {
  try {
    const { data: licenseData } = await LicenseService($client).fetch(
      route.params.id
    )
    return licenseData
  } catch {
    throw createError({
      statusCode: 404,
      message: 'The license was not found.',
    })
  }
})

const license = computed(() => data.value)

const checkLoading = ref(false)
const disconnectModal = ref(null)

const licenseType = computed(() => {
  if (!license.value) return null
  return $registry.get('license', license.value.product_code)
})

const licenseFeatureDescription = computed(() => {
  if (!licenseType.value) return []
  return licenseType.value.getFeaturesDescription()
})

function localDateTime(timestamp) {
  if (timestamp === null) {
    return ''
  }
  return moment.utc(timestamp).local().format('ll LT')
}

async function check() {
  checkLoading.value = true

  try {
    const { data: responseData, status } = await LicenseService($client).check(
      license.value.id
    )
    if (status === 204) {
      router.push({ name: 'admin-licenses' })
    } else {
      data.value = responseData
    }
  } catch (error) {
    notifyIf(error)
  }

  checkLoading.value = false
}
</script>
