<template>
  <form @submit.prevent>
    <LocalBaserowServiceForm
      :application="application"
      :default-values="defaultValues"
      @values-changed="emitServiceChange($event)"
    ></LocalBaserowServiceForm>
  </form>
</template>

<script>
import { defineComponent, ref } from 'vue'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'
import _ from 'lodash'

export default defineComponent({
  name: 'LocalBaserowSignalTriggerServiceForm',
  components: { LocalBaserowServiceForm },
  props: {
    application: {
      type: Object,
      required: true,
    },
    service: {
      type: Object,
      required: true,
    },
  },
  emits: ['values-changed'],
  setup(props, { emit }) {
    const defaultValues = ref({})
    defaultValues.value = { ...props.service }

    const emitServiceChange = (newValues) => {
      const updated = { ...defaultValues, ...newValues }
      const differences = Object.fromEntries(
        Object.entries(updated).filter(
          ([key, value]) => !_.isEqual(value, defaultValues[key])
        )
      )
      emit('values-changed', differences)
    }

    return {
      defaultValues,
      emitServiceChange,
    }
  },
})
</script>
