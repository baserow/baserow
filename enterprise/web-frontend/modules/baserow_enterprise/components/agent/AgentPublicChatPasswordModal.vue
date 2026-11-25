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
      <Error :error="error" />
      <form class="agent-public-chat-password-modal" @submit.prevent="submit">
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
            :disabled="loading"
            @click="modal.hide()"
          >
            {{ $t('action.cancel') }}
          </Button>
          <Button
            type="primary"
            size="large"
            button-type="submit"
            class="agent-public-chat-password-modal__save"
            :loading="loading"
            :disabled="loading || v$.$invalid"
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

/** Asks for the password of a public chat and stays open until it is saved. */
const props = defineProps({
  /** Whether the public chat already has a password, which this changes. */
  change: Boolean,
  /** Saves the password, and rejects when that fails. */
  save: { type: Function, required: true },
})
const modal = ref(null)
const loading = ref(false)
const error = reactive({ visible: false, title: '', message: '' })
const values = reactive({ password: '' })
const v$ = useVuelidate({ password: passwordValidation }, values, {
  $lazy: true,
})

function show() {
  values.password = ''
  v$.value.$reset()
  error.visible = false
  modal.value.show()
  nextTick(() =>
    modal.value.getTeleportedElement()?.querySelector('input')?.focus()
  )
}

async function submit() {
  v$.value.$touch()
  if (v$.value.$invalid) return
  error.visible = false
  loading.value = true
  try {
    await props.save(values.password)
    values.password = ''
    modal.value.hide()
  } catch (caught) {
    if (!caught.handler) throw caught
    Object.assign(error, caught.handler.getMessage('channel'), {
      visible: true,
    })
    caught.handler.handled()
  } finally {
    loading.value = false
  }
}

defineExpose({ show })
</script>
