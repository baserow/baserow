<template>
  <div class="form-view__page-container">
    <Toasts></Toasts>
    <div class="form-view__page">
      <div v-if="fields.length === 0" class="form-view__body">
        <div class="form-view__no-fields margin-bottom-4">
          <div class="form-view__no-fields-title">
            This form doesn't have any fields
          </div>
          <div class="form-view__no-fields-content">
            Use Baserow to add at least one field.
          </div>
        </div>
        <FormViewPoweredBy v-if="showLogo"></FormViewPoweredBy>
      </div>
      <component
        :is="component"
        v-else
        ref="form"
        v-model="values"
        :loading="loading"
        :submitted="submitted"
        :title="title"
        :description="description"
        :cover-image="coverImage"
        :logo-image="logoImage"
        :submit-text="submitText"
        :all-fields="fields"
        :visible-fields="visibleFields"
        :is-redirect="isRedirect"
        :submit-action-redirect-url="submitActionRedirectUrl"
        :submit-action-message="submitActionMessage"
        :show-logo="showLogo"
        @submit="submit"
      ></component>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useAsyncData } from '#app'
import { useHead } from '#imports'
import { useRoute, useRouter } from 'vue-router'

import { clone, isPromise } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import FormService from '@baserow/modules/database/services/view/form'
import {
  getHiddenFieldNames,
  getPrefills,
  prefillField,
} from '@baserow/modules/database/utils/form'
import { matchSearchFilters } from '@baserow/modules/database/utils/view'
import FormViewPoweredBy from '@baserow/modules/database/components/view/form/FormViewPoweredBy'

definePageMeta({
  middleware: ['settings'],
})

const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()
const { $store, $client, $registry } = nuxtApp

const loading = ref(false)
const submitted = ref(false)
const submitAction = ref('MESSAGE')
const submitActionMessage = ref('')
const submitActionRedirectUrl = ref('')

const form = ref(null)

// Replaces asyncData from Nuxt2
const { data, error } = await useAsyncData(
  `database-public-form-${route.params.slug}`,
  async () => {
    const slug = route.params.slug

    const publicAuthToken = await $store.dispatch(
      'page/view/public/setAuthTokenFromCookiesIfNotSet',
      { slug }
    )

    let responseData = null
    try {
      const { data } = await FormService($client).getMetaInformation(
        slug,
        publicAuthToken
      )
      responseData = data
    } catch (e) {
      const statusCode = e.response?.status

      // password protect forms require authentication
      if (statusCode === 401) {
        // Combine the path and query parameters to get the full URL
        const path = route.path
        const queryParams = route.query
        const queryString = Object.keys(queryParams).length
          ? '?' + new URLSearchParams(queryParams).toString()
          : ''
        const original = path + queryString

        return {
          redirect: router.resolve({
            name: 'database-public-view-auth',
            query: { original },
          }),
        }
      } else {
        throw createError({ statusCode: 404, message: 'Form not found.' })
      }
    }

    // Build initial values object
    const values = {}
    const prefills = getPrefills(route.query)
    const hiddenFields = getHiddenFieldNames(route.query)
    const promises = []

    responseData.fields.forEach((field) => {
      field._ = {
        touched: false,
        hiddenViaQueryParam: hiddenFields.includes(field.name),
      }
      const fieldType = $registry.get('field', field.field.type)
      const setValue = (value) => {
        values[`field_${field.field.id}`] = value
      }

      const prefill = prefillField(field, prefills)

      values[`field_${field.field.id}`] = fieldType.getDefaultValue(field.field)

      if (
        prefill !== undefined &&
        prefill !== null &&
        fieldType.canParseQueryParameter()
      ) {
        const result = fieldType.parseQueryParameter(field, prefill, {
          slug,
          client: $client,
          publicAuthToken,
        })

        if (isPromise(result)) {
          result.then(setValue)
          promises.push(result)
        } else {
          setValue(result)
        }
      }
    })

    await Promise.all(promises)

    // Sort fields immediately (SSR order)
    responseData.fields = responseData.fields.sort((a, b) => {
      if (a.order > b.order) return 1
      if (a.order < b.order) return -1

      if (a.field.id < b.field.id) return -1
      if (a.field.id > b.field.id) return 1
      return 0
    })

    return {
      title: responseData.title,
      description: responseData.description,
      coverImage: responseData.cover_image,
      logoImage: responseData.logo_image,
      submitText: responseData.submit_text,
      fields: responseData.fields,
      mode: responseData.mode,
      showLogo: responseData.show_logo,
      values,
      publicAuthToken,
    }
  },
  // Ensure re-fetch if the URL (incl. query) changes while reusing the page instance
  { watch: [() => route.fullPath] }
)

if (error.value) {
  if (error.value.statusCode === 404) {
    showError(error.value)
  } else {
    throw error.value
  }
}

if (data.value?.redirect) {
  await navigateTo(data.value.redirect.href)
}

// Expose data like the old asyncData return did
const title = computed(() => data.value.title)
const description = computed(() => data.value.description)
const coverImage = computed(() => data.value.coverImage)
const logoImage = computed(() => data.value.logoImage)
const submitText = computed(() => data.value.submitText)
const fields = computed(() => data.value.fields || [])
const mode = computed(() => data.value.mode)
const showLogo = computed(() => data.value.showLogo)
const publicAuthToken = computed(() => data.value.publicAuthToken)
const values = ref(data.value.values)

useHead(() => {
  const head = {
    title: title.value || 'Form',
    bodyAttrs: {
      class: ['background-white'],
    },
  }
  if (!showLogo.value) {
    head.titleTemplate = '%s'
  }
  return head
})

const isRedirect = computed(() => {
  return (
    submitAction.value === 'REDIRECT' && submitActionRedirectUrl.value !== ''
  )
})

const visibleFields = computed(() => {
  return fields.value.reduce((visible, field, index) => {
    // If the conditional visibility is disabled, we must always show the field.
    if (!field.show_when_matching_conditions) {
      return [...visible, field]
    }

    // A condition is only valid if the filter field is before this field.
    const fieldsBefore = fields.value.slice(0, index).map((f) => f.field)

    // Find valid filters
    const conditions = field.conditions.filter((condition) => {
      const filterType = $registry.get('viewFilter', condition.type)
      const filterField = fieldsBefore.find((f) => f.id === condition.field)
      return (
        filterField !== undefined && filterType.fieldIsCompatible(filterField)
      )
    })

    const conditionType = field.condition_type

    // If there aren't any conditions, we must always show the field.
    if (conditions.length === 0) {
      return [...visible, field]
    }

    // Only work with values of fields that are actually visible.
    const visibleFieldIds = visible.map((f) => f.field.id)
    const visibleValues = clone(values.value)

    fields.value
      .filter(
        (f) =>
          !visibleFieldIds.includes(f.field.id) && f.field.id !== field.field.id
      )
      .forEach((f) => {
        visibleValues['field_' + f.field.id] = $registry
          .get('field', f.field.type)
          .getDefaultValue(f.field)
      })

    if (
      matchSearchFilters(
        conditionType,
        conditions,
        field.condition_groups,
        fieldsBefore,
        visibleValues
      )
    ) {
      return [...visible, field]
    }

    return visible
  }, [])
})

const component = computed(() => {
  return $registry.get('formViewMode', mode.value).getFormComponent()
})

function touch() {
  visibleFields.value.forEach((field) => {
    field._.touched = true
  })
}

async function submit() {
  if (loading.value) {
    return
  }

  touch()
  loading.value = true

  const valuesCopy = clone(values.value)
  const submitValues = {}

  // Loop over visible fields only
  for (let i = 0; i < visibleFields.value.length; i++) {
    const field = visibleFields.value[i]
    const fieldType = $registry.get('field', field.field.type)
    const valueName = `field_${field.field.id}`
    const value = valuesCopy[valueName]
    const ref = form.value?.$refs?.['field-' + field.field.id]?.[0]

    if (
      (field.required && fieldType.isEmpty(field.field, value)) ||
      fieldType.getValidationError(field.field, value) !== null ||
      !ref.isValid()
    ) {
      ref.focus()
      loading.value = false
      return
    }

    submitValues[valueName] = fieldType.prepareValueForUpdate(
      field.field,
      valuesCopy[valueName]
    )
  }

  try {
    const slug = route.params.slug
    const { data: submitResponse } = await FormService($client).submit(
      slug,
      submitValues,
      publicAuthToken.value
    )

    submitted.value = true
    submitAction.value = submitResponse.submit_action
    submitActionMessage.value = submitResponse.submit_action_message
    submitActionRedirectUrl.value =
      submitResponse.submit_action_redirect_url.replace(
        `{row_id}`,
        submitResponse.row_id
      )

    if (isRedirect.value) {
      setTimeout(() => {
        window.location.assign(submitActionRedirectUrl.value)
      }, 4000)
    }
  } catch (err) {
    notifyIf(err, 'view')
  }

  loading.value = false
}
</script>
