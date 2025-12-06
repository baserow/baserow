<template>
  <form @submit.prevent>
    <FormGroup
      :label="$t('positionedContainerElementForm.alignment')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.alignment" :show-search="false" small>
        <DropdownItem
          v-for="alignment in alignmentOptions"
          :key="alignment.value"
          :name="alignment.name"
          :value="alignment.value"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup
      :label="$t('positionedContainerElementForm.behaviour')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.behaviour" :show-search="false" small>
        <DropdownItem
          v-for="behaviour in behaviourOptions"
          :key="behaviour.value"
          :name="behaviour.name"
          :value="behaviour.value"
        />
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'PositionedContainerElementForm',
  mixins: [form],

  data() {
    return {
      values: {
        alignment: 'top',
        behaviour: 'fixed',
      },
    }
  },

  mounted() {
    // Load existing element values into form
    this.values.alignment = this.defaultValues.alignment
    this.values.behaviour = this.defaultValues.behaviour
  },

  watch: {
    values: {
      handler() {
        this.$emit('input', this.values)
      },
      deep: true,
    },
  },

  computed: {
    alignmentOptions() {
      return [
        {
          value: 'top',
          name: this.$t('positionedContainerElementForm.alignmentTop'),
        },
        {
          value: 'bottom',
          name: this.$t('positionedContainerElementForm.alignmentBottom'),
        },
      ]
    },
    behaviourOptions() {
      return [
        {
          value: 'fixed',
          name: this.$t('positionedContainerElementForm.behaviourFixed'),
        },
      ]
    },
  },
}
</script>
