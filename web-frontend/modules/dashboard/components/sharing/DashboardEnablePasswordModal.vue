<template>
  <Modal ref="modal" :small="true">
    <h2 class="box__title">{{ $t(titleText) }}</h2>
    <Error :error="error"></Error>
    <form @submit.prevent="setPassword">
      <p class="box__description">{{ $t(descriptionText) }}</p>
      <div class="margin-bottom-2">
        <PasswordInput
          v-model="v$.values.password.$model"
          :validation-state="v$.values.password"
          :placeholder="$t('dashboardEnablePasswordModal.placeholder')"
        />
      </div>
      <div class="actions actions--right actions--gap">
        <Button
          type="secondary"
          size="large"
          button-type="button"
          :disabled="loading"
          @click.prevent="hide()"
        >
          {{ $t('action.cancel') }}
        </Button>
        <Button
          type="primary"
          size="large"
          button-type="submit"
          :loading="loading"
          :disabled="loading || v$.$invalid"
        >
          {{ $t(saveText) }}
        </Button>
      </div>
    </form>
  </Modal>
</template>

<script>
import { computed, reactive } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { passwordValidation } from '@baserow/modules/core/validators'
import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'
import { updateDashboardSharing } from '@baserow/modules/dashboard/utils/sharing'

/**
 * Sets or changes the password of a publicly shared dashboard. The `modal` and
 * `error` mixins only exist for the options API, which is why this component
 * doesn't use the composition API.
 */
export default {
  name: 'DashboardEnablePasswordModal',
  components: { PasswordInput },
  mixins: [modal, error],
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
  },
  setup() {
    const values = reactive({
      values: {
        password: '',
      },
    })

    const rules = computed(() => ({
      values: {
        password: passwordValidation,
      },
    }))

    return {
      values: values.values,
      v$: useVuelidate(rules, values, { $lazy: true }),
    }
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    change() {
      return this.dashboard.public_has_password
    },
    titleText() {
      return this.change
        ? 'dashboardEnablePasswordModal.changeTitle'
        : 'dashboardEnablePasswordModal.title'
    },
    descriptionText() {
      return this.change
        ? 'dashboardEnablePasswordModal.changeDescription'
        : 'dashboardEnablePasswordModal.description'
    },
    saveText() {
      return this.change
        ? 'dashboardEnablePasswordModal.changePassword'
        : 'dashboardEnablePasswordModal.setPassword'
    },
  },
  methods: {
    show(...args) {
      this.values.password = ''
      this.v$.$reset()
      this.hideError()
      modal.methods.show.call(this, ...args)
      this.$nextTick(() => {
        this.getTeleportedElement()?.querySelector('input')?.focus()
      })
    },
    async setPassword() {
      // The validation is lazy, so an untouched password hasn't been checked
      // yet and must not reach the backend, where an empty one removes the
      // password.
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }

      this.hideError()
      this.loading = true

      try {
        await updateDashboardSharing(this, this.dashboard, {
          public_password: this.values.password,
        })
        this.hide()
      } catch (error) {
        this.handleError(error, 'application')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
