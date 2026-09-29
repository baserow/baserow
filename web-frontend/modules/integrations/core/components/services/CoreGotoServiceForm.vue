<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('coreGotoServiceForm.conditionLabel')"
      required
      class="margin-bottom-2"
    >
      <p class="margin-top-0 margin-bottom-1">
        {{ $t('coreGotoServiceForm.conditionDescription') }}
      </p>
      <InjectedFormulaInput
        v-model="values.condition"
        :placeholder="$t('coreGotoServiceForm.conditionPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('coreGotoServiceForm.destinationLabel')"
      required
    >
      <p class="margin-top-0 margin-bottom-1">
        {{ $t('coreGotoServiceForm.destinationDescription') }}
      </p>
      <Dropdown
        v-model="values.destination_service_id"
        :placeholder="$t('coreGotoServiceForm.destinationPlaceholder')"
      >
        <DropdownItem
          v-for="destination in destinations"
          :key="destination.value"
          :name="destination.name"
          :value="destination.value"
        />
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'CoreGotoServiceForm',
  components: { InjectedFormulaInput },
  mixins: [form],
  props: {
    service: {
      type: Object,
      required: false,
      default: null,
    },
    /**
     * The selectable jump targets, as `{ value, name }` where `value` is the
     * destination service id. The form stays generic: the caller (e.g. the
     * automation `NodeSidePanel`) works out which destinations are valid and
     * what to call them, so this form never reaches into automation nodes.
     */
    destinations: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  data() {
    return {
      allowedValues: ['condition', 'destination_service_id'],
      values: {
        condition: {},
        destination_service_id: null,
      },
    }
  },
  watch: {
    /**
     * The `form` mixin seeds `values` from `defaultValues` only once, so an
     * external change to the destination (e.g. a move clears the link because
     * it took the destination off the goto node's path) wouldn't otherwise
     * reach the dropdown. Adopt such changes here.
     */
    service(service) {
      const destinationServiceId = service?.destination_service_id ?? null
      if (destinationServiceId !== this.values.destination_service_id) {
        this.values.destination_service_id = destinationServiceId
      }
    },
  },
}
</script>
