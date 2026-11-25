<template>
  <Modal ref="modal" small>
    <template #content>
      <h2 class="box__title">
        {{
          $t(
            change
              ? 'agentChannels.changePassword'
              : 'agentChannels.passwordTitle'
          )
        }}
      </h2>
      <form class="agent-public-chat-password-modal" @submit.prevent="save">
        <p class="box__description">
          {{
            $t(
              change
                ? 'agentChannels.changePasswordDescription'
                : 'agentChannels.passwordDescription'
            )
          }}
        </p>
        <div class="margin-bottom-2">
          <PasswordInput
            v-model="v$.password.$model"
            class="agent-public-chat-password-modal__input"
            :validation-state="v$.password"
            :placeholder="$t('agentChannels.password')"
          />
        </div>
        <div class="actions actions--right actions--gap">
          <Button
            type="secondary"
            size="large"
            button-type="button"
            @click="modal.hide()"
          >
            {{ $t('action.cancel') }}
          </Button>
          <Button
            type="primary"
            size="large"
            button-type="submit"
            class="agent-public-chat-password-modal__save"
            :disabled="v$.$invalid"
          >
            {{
              $t(
                change
                  ? 'agentChannels.changePassword'
                  : 'agentChannels.setPassword'
              )
            }}
          </Button>
        </div>
      </form>
    </template>
  </Modal>
</template>

<script setup>
import { nextTick, reactive, ref } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import { passwordValidation } from '@baserow/modules/core/validators'
import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'

/** Asks for the password of a public chat, which is forgotten once emitted. */
defineProps({
  /** Whether the public chat already has a password, which this changes. */
  change: Boolean,
})
const emit = defineEmits(['save'])
const modal = ref(null)
const values = reactive({ password: '' })
const v$ = useVuelidate({ password: passwordValidation }, values, {
  $lazy: true,
})

function show() {
  values.password = ''
  v$.value.$reset()
  modal.value.show()
  nextTick(() =>
    modal.value.getTeleportedElement()?.querySelector('input')?.focus()
  )
}

function save() {
  v$.value.$touch()
  if (v$.value.$invalid) return
  emit('save', values.password)
  values.password = ''
  modal.value.hide()
}

defineExpose({ show })
</script>
