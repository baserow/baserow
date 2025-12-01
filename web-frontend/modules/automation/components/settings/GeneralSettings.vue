<template>
  <div>
    <h2 class="box__title">{{ $t('generalSettings.titleOverview') }}</h2>

    <FormGroup
      small-label
      :label="$t('generalSettings.nameLabel')"
      :error="fieldHasErrors('name')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        v-model="v$.values.name.$model"
        :error="fieldHasErrors('name')"
        size="large"
      ></FormInput>
      <template #error>
        {{ v$.values.name.$errors[0].$message }}
      </template>
    </FormGroup>

    <div class="separator"></div>

    <FormGroup
      small-label
      :label="$t('generalSettings.notificationLabel')"
      :error="fieldHasErrors('notification')"
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="v$.values.notification.$model" class="margin-top-1">{{
        $t('generalSettings.notificationCheckboxLabel')
      }}</Checkbox>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import {
  reactive,
  getCurrentInstance,
  defineComponent,
  toRefs,
  watch,
} from 'vue'
import { useStore, useContext } from '@nuxtjs/composition-api'
import { required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import { isSubObject } from '@baserow/modules/core/utils/object'

export default defineComponent({
  name: 'GeneralSettings',
  mixins: [form],
  props: {
    automation: {
      type: Object,
      required: true,
    },
  },

  setup(props) {
    const instance = getCurrentInstance()
    const { app } = useContext()
    const i18n = app.i18n
    const store = useStore()
    const { automation } = toRefs(props)

    const values = reactive({
      values: {
        name: '',
        notification: false,
      },
    })

    const rules = {
      values: {
        name: {
          required: helpers.withMessage(
            i18n.t('error.requiredField'),
            required
          ),
        },
        notification: {},
      },
    }

    const v$ = useVuelidate(rules, values, { $lazy: true })

    const updateAutomation = async (updatedValues) => {
      if (isSubObject(automation.value, updatedValues)) {
        return
      }

      try {
        await store.dispatch('application/update', {
          automation: automation.value,
          values: updatedValues,
        })
      } catch (error) {
        const title = i18n.t('generalSettings.cantUpdateAutomationTitle')
        const message = i18n.t(
          'generalSettings.cantUpdateAutomationDescription'
        )
        store.dispatch('toast/error', { title, message })
        instance.proxy.reset()
      }
    }

    watch(
      () => values.values,
      (newValues) => {
        updateAutomation(newValues)
      },
      { deep: true }
    )

    return {
      values: values.values,
      v$,
      updateAutomation,
    }
  },
})
</script>
