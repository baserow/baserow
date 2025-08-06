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

<script>
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

export default {
  components: {
    Toasts,
    FormViewPoweredBy,
  },
  middleware: ['settings'],
  async asyncData({ params, error, app, route, redirect, store }) {
    const slug = params.slug
    const publicAuthToken = await store.dispatch(
      'page/view/public/setAuthTokenFromCookiesIfNotSet',
      { slug }
    )

    let data = null
    try {
      const { data: responseData } = await FormService(
        app.$client
      ).getMetaInformation(slug, publicAuthToken)
      data = responseData
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
        return redirect({
          name: 'database-public-view-auth',
          query: { original },
        })
      } else {
        return error({ statusCode: 404, message: 'Form not found.' })
      }
    }

    // After the form field metadata has been fetched, we need to make the values
    // object with the empty field value as initial form value.
    const values = {}
    const prefills = getPrefills(route.query)
    const hiddenFields = getHiddenFieldNames(route.query)
    const promises = []
    data.fields.forEach((field) => {
      field._ = {
        touched: false,
        hiddenViaQueryParam: hiddenFields.includes(field.name),
      }
      const fieldType = app.$registry.get('field', field.field.type)
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
          client: app.$client,
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

    // Order the fields directly after fetching the results to make sure the form is
    // serverside rendered in the right order.
    data.fields = data.fields.sort((a, b) => {
      // First by order.
      if (a.order > b.order) {
        return 1
      } else if (a.order < b.order) {
        return -1
      }

      // Then by id.
      if (a.field.id < b.field.id) {
        return -1
      } else if (a.field.id > b.field.id) {
        return 1
      } else {
        return 0
      }
    })

    return {
      title: data.title,
      description: data.description,
      coverImage: data.cover_image,
      logoImage: data.logo_image,
      submitText: data.submit_text,
      fields: data.fields,
      mode: data.mode,
      showLogo: data.show_logo,
      values,
      publicAuthToken,
    }
  },
  data() {
    return {
      loading: false,
      submitted: false,
      submitAction: 'MESSAGE',
      submitActionMessage: '',
      submitActionRedirectUrl: '',
    }
  },
  head() {
    const head = {
      title: this.title || 'Form',
      bodyAttrs: {
        class: ['background-white'],
      },
    }
    if (!this.showLogo) {
      head.titleTemplate = '%s'
    }
    return head
  },
  computed: {
    isRedirect() {
      return (
        this.submitAction === 'REDIRECT' && this.submitActionRedirectUrl !== ''
      )
    },
    /**
     * Returns all the fields that should be visible to the visitor. They can change
     * depending on the values because some fields have conditions whether they
     * should be visible.
     */
    visibleFields() {
      return this.fields.reduce((visibleFields, field, index, tmp) => {
        // If the conditional visibility is disabled, we must always show the field.
        if (!field.show_when_matching_conditions) {
          return [...visibleFields, field]
        }

        // A condition is only valid if the filter field is before this field because
        // you can only filter fields before. Therefore, we check which fields are
        // before.
        const fieldsBefore = this.fields.slice(0, index).map((f) => f.field)
        // Find the valid filters by checking if the filter field is before this field
        // and if the filter type is compatible with the field.
        const conditions = field.conditions.filter((condition) => {
          const filterType = this.$registry.get('viewFilter', condition.type)
          const filterField = fieldsBefore.find((f) => f.id === condition.field)
          return (
            filterField !== undefined &&
            filterType.fieldIsCompatible(filterField)
          )
        })
        const conditionType = field.condition_type

        // If there aren't any conditions, we must always show the field.
        if (conditions.length === 0) {
          return [...visibleFields, field]
        }

        // We only want to work with the values of fields that are actually visible.
        // This to avoid matching the conditions on values of fields that aren't
        // visible, but were filled out in the past and are still remembered in memory.
        const visibleFieldIds = visibleFields.map((f) => f.field.id)
        const visibleValues = clone(this.values)
        this.fields
          .filter(
            (f) =>
              !visibleFieldIds.includes(f.field.id) &&
              f.field.id !== field.field.id
          )
          .forEach((f) => {
            visibleValues['field_' + f.field.id] = this.$registry
              .get('field', f.field.type)
              .getDefaultValue(f.field)
          })

        if (
          matchSearchFilters(
            this.$registry,
            conditionType,
            conditions,
            field.condition_groups,
            fieldsBefore,
            visibleValues
          )
        ) {
          return [...visibleFields, field]
        }

        return visibleFields
      }, [])
    },
    component() {
      return this.$registry.get('formViewMode', this.mode).getFormComponent()
    },
  },
  methods: {
    async submit() {
      if (this.loading) {
        return
      }

      this.touch()
      this.loading = true
      const values = clone(this.values)
      const submitValues = {}

      // Loop over the visible fields, because we only want to submit those values.
      for (let i = 0; i < this.visibleFields.length; i++) {
        const field = this.visibleFields[i]
        const fieldType = this.$registry.get('field', field.field.type)
        const valueName = `field_${field.field.id}`
        const value = values[valueName]
        const ref = this.$refs.form.$refs['field-' + field.field.id][0]

        // If the field is required but empty or if the value has a validation error, then
        // we don't want to submit the form, focus on the field and stop the loading.
        if (
          (field.required && fieldType.isEmpty(field.field, value)) ||
          fieldType.getValidationError(field.field, value) !== null ||
          // It could be that the field component is in an invalid state and hasn't
          // update the value yet. In that case, we also don't want to submit the form.
          !ref.isValid()
        ) {
          ref.focus()
          this.loading = false
          return
        }

        submitValues[valueName] = fieldType.prepareValueForUpdate(
          field.field,
          values[valueName]
        )
      }

      try {
        const slug = this.$route.params.slug
        const { data } = await FormService(this.$client).submit(
          slug,
          submitValues,
          this.publicAuthToken
        )

        this.submitted = true
        this.submitAction = data.submit_action
        this.submitActionMessage = data.submit_action_message
        this.submitActionRedirectUrl = data.submit_action_redirect_url.replace(
          `{row_id}`,
          data.row_id
        )

        // If the submit action is a redirect, then we need to redirect safely to the
        // provided URL.
        if (this.isRedirect) {
          setTimeout(() => {
            window.location.assign(this.submitActionRedirectUrl)
          }, 4000)
        }
      } catch (error) {
        notifyIf(error, 'view')
      }
      this.loading = false
    },
    /**
     * Marks all the fields are touched. This will show any validation error messages
     * if there are any.
     */
    touch() {
      this.visibleFields.forEach((field) => {
        field._.touched = true
      })
    },
  },
}
</script>
