<template>
  <form @submit.prevent>
    <LocalBaserowServiceForm
      :application="automation"
      :default-values="defaultValues"
      @values-changed="emitServiceChange($event)"
    ></LocalBaserowServiceForm>
  </form>
</template>

<script>
import { defineComponent, ref, inject } from 'vue'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'
import _ from 'lodash'

export default defineComponent({
  name: 'LocalBaserowRowsCreatedServiceForm',
  components: { LocalBaserowServiceForm },
  props: {
    node: {
      type: Object,
      required: true,
    },
  },
  emits: ['values-changed'],
  setup(props, { emit }) {
    const automation = inject('automation')

    const defaultValues = ref({})
    defaultValues.value = { ...props.node.service }

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
      automation,
      defaultValues,
      emitServiceChange,
    }
  },
})
</script>
