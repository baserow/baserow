<template>
  <Modal ref="modal" :small="true">
    <h2 class="box__title">
      {{
        hasPassword
          ? $t('invitationLinkPasswordModal.changeTitle')
          : $t('invitationLinkPasswordModal.newTitle')
      }}
    </h2>
    <Error :error="error"></Error>
    <form @submit.prevent="save(values.password)">
      <p class="box__description">
        {{ $t('invitationLinkPasswordModal.description') }}
      </p>
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
          <li v-if="hasPassword">
            <a :disabled="loading" @click.prevent="save('')">
              {{ $t('invitationLinkPasswordModal.remove') }}
            </a>
          </li>
          <li v-else>
            <a :disabled="loading" @click.prevent="hide()">
              {{ $t('action.cancel') }}
            </a>
          </li>
        </ul>
        <Button
          type="primary"
          :loading="loading"
          :disabled="loading || v$.$invalid"
        >
          {{ $t('invitationLinkPasswordModal.save') }}
        </Button>
      </div>
    </form>
  </Modal>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { passwordValidation } from '@baserow/modules/core/validators'
import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'

/**
 * Sets, changes or removes the password that people must enter before they
 * can use an invitation link. Changing it locks out everyone who only knew the
 * previous password, including those who already entered it.
 */
export default {
  name: 'InvitationLinkPasswordModal',
  components: { PasswordInput },
  mixins: [form, modal, error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    target: {
      type: Object,
      required: true,
    },
    targetType: {
      type: Object,
      required: true,
    },
  },
  emits: ['updated'],
  setup() {
    const values = reactive({ values: { password: '' } })
    const rules = { values: { password: passwordValidation } }
    return {
      values: values.values,
      v$: useVuelidate(rules, values, { $lazy: true }),
    }
  },
  data() {
    return {
      loading: false,
      invitationLink: null,
      allowedValues: ['password'],
    }
  },
  computed: {
    hasPassword() {
      return Boolean(this.invitationLink?.has_password)
    },
  },
  methods: {
    show(invitationLink, ...args) {
      this.invitationLink = invitationLink
      this.values.password = ''
      this.v$.$reset()
      this.hideError()
      modal.methods.show.call(this, ...args)
      this.$nextTick(() => {
        this.getTeleportedElement()?.querySelector('input')?.focus()
      })
    },
    async save(password) {
      this.hideError()
      this.loading = true
      try {
        const updated = await this.targetType.updateInvitationLink(
          this.workspace,
          this.target,
          this.invitationLink,
          { password }
        )
        this.$emit('updated', this.invitationLink, updated)
        this.hide()
      } catch (error) {
        this.handleError(error)
      }
      this.loading = false
    },
  },
}
</script>
