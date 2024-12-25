<template>
  <FormGroup>
    <Dropdown
      :value="workflowActionType.getType()"
      :show-search="false"
      :disabled="disabled"
      @change="$emit('change', $event)"
    >
      <DropdownItem
        v-for="availableWorkflowActionType in availableWorkflowActionTypes"
        :key="availableWorkflowActionType.getType()"
        :name="availableWorkflowActionType.label"
        :value="availableWorkflowActionType.getType()"
      ></DropdownItem>
    </Dropdown>

    <template #after-input>
      <ButtonIcon icon="iconoir-bin" @click="$emit('delete')" />
    </template>
  </FormGroup>
</template>

<script>
export default {
  name: 'WorkflowActionSelector',
  props: {
    availableWorkflowActionTypes: {
      type: Array,
      required: true,
    },
    workflowAction: {
      type: Object,
      required: false,
      default: null,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    workflowActionType() {
      return this.availableWorkflowActionTypes.find(
        (workflowActionType) =>
          workflowActionType.getType() === this.workflowAction.type
      )
    },
  },
}
</script>
