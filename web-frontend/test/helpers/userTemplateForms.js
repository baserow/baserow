import { flushPromises } from '@vue/test-utils'

export const chooseVisibility = async (wrapper, label) => {
  await wrapper
    .findAll('.segment-control__button')
    .find((button) => button.text() === label)
    .trigger('click')
  await flushPromises()
}

export const selectWorkspace = async (wrapper, workspaceId) => {
  wrapper
    .findComponent({ name: 'Dropdown' })
    .vm.$emit('update:modelValue', workspaceId)
  await flushPromises()
}

export const selectApplications = async (wrapper, applicationIds) => {
  wrapper
    .findComponent({ name: 'ApplicationSelector' })
    .vm.$emit('update', applicationIds)
  await flushPromises()
}

export const selectedApplicationIds = (wrapper) =>
  wrapper
    .findComponent({ name: 'ApplicationSelector' })
    .props('selectedApplicationIds')
