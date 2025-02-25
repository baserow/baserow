<template>
  <Modal :small="true">
    <h2 class="box__title">{{ $t(titleText) }}</h2>
    <Error :error="error"></Error>
    <form @submit.prevent="setPassword">
      <p class="box__description">{{ $t(descriptionText) }}</p>
      <FormGroup :error="fieldHasErrors('password')">
        <PasswordInput
          v-model="v$.values.password.$model"
          :validation-state="v$.values.password"
          :show-password-icon="true"
          :disabled="loading"
        />
      </FormGroup>
      <div class="actions">
        <ul class="action__links">
          <li>
            <a :disabled="loading" @click.prevent="hide()">{{
              $t('action.cancel')
            }}</a>
          </li>
        </ul>
        <Button
          type="primary"
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
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { passwordValidation } from '@baserow/modules/core/validators'
import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'

export default {
  name: 'ShareViewPasswordModal',
  components: { PasswordInput },
  mixins: [form, modal, error],
  props: {
    view: {
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
      allowedValues: ['password'],
    }
  },
  computed: {
    change() {
      return this.view.public_view_has_password
    },
    titleText() {
      return this.change
        ? 'shareViewEnablePasswordModal.changePasswordTitle'
        : 'shareViewEnablePasswordModal.newPasswordTitle'
    },
    descriptionText() {
      return this.change
        ? 'shareViewEnablePasswordModal.changePasswordDescription'
        : 'shareViewEnablePasswordModal.newPasswordDescription'
    },
    saveText() {
      return this.change
        ? 'shareViewEnablePasswordModal.changePasswordSave'
        : 'shareViewEnablePasswordModal.newPasswordSave'
    },
  },
  methods: {
    clearInput() {
      this.values.password = ''
      this.v$.$reset()
    },
    show() {
      this.clearInput()
      modal.methods.show.bind(this)()
      this.$nextTick(() => {
        this.$el.querySelector('input')?.focus()
      })
    },
    async setPassword() {
      this.hideError()
      this.loading = true

      const view = this.view
      try {
        await this.$store.dispatch('view/update', {
          view,
          values: { public_view_password: this.values.password },
        })

        this.hide()
      } catch (error) {
        this.handleError(error, 'table')
      }

      this.loading = false
    },
  },
}
</script>
