import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import MockAdapter from 'axios-mock-adapter'

import CoreRunAgentServiceForm from '@baserow_enterprise/integrations/core/components/services/CoreRunAgentServiceForm'
import { CoreRunAgentServiceType } from '@baserow_enterprise/integrations/core/serviceTypes'

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  template: '<div class="formula-stub" />',
})

const serviceType = {
  getDefaultValues(service, values) {
    return values
  },
}

async function mountForm({ provide = {}, defaultValues = {} } = {}) {
  const { $store, $client } = useNuxtApp()
  // Selecting a workspace fetches its permissions.
  new MockAdapter($client).onGet('workspaces/1/permissions/').reply(200, [])
  const workspace = { id: 1, name: 'Workspace' }
  await $store.dispatch('workspace/forceCreate', workspace)
  await $store.dispatch('workspace/select', workspace)
  await $store.dispatch('application/forceCreate', {
    id: 10,
    type: 'agent',
    name: 'Support agent',
    order: 1,
    workspace,
    tables: [],
  })
  await $store.dispatch('application/forceCreate', {
    id: 11,
    type: 'database',
    name: 'CRM',
    order: 2,
    workspace,
    tables: [],
  })
  return await mountSuspended(CoreRunAgentServiceForm, {
    props: { defaultValues, service: null, serviceType },
    global: {
      provide,
      stubs: { InjectedFormulaInput: InjectedFormulaInputStub },
    },
  })
}

describe('Run agent service form', () => {
  test('offers the workspace agents and the wait switch', async () => {
    const wrapper = await mountForm()
    const items = wrapper.findAll('.select__item').map((item) => item.text())
    expect(items).toContain('Support agent')
    expect(items).not.toContain('CRM')
    expect(wrapper.find('.checkbox').exists()).toBe(true)
  })

  test('hides the wait switch inside the application builder', async () => {
    const wrapper = await mountForm({
      provide: { applicationContext: { builder: { id: 5 } } },
    })
    expect(wrapper.find('.checkbox').exists()).toBe(false)
  })

  test('the service type reports a missing agent', () => {
    const { $registry } = useNuxtApp()
    const type = new CoreRunAgentServiceType({ app: useNuxtApp() })
    expect(
      type.getErrorMessage({ service: { agent_application_id: null } })
    ).toBe('serviceType.errorNoAgentSelected')
    expect(type.getDataSchema({}, { schema: { type: 'object' } })).toEqual({
      type: 'object',
    })
    expect($registry.get('service', 'run_agent')).toBeTruthy()
    expect($registry.get('node', 'run_agent')).toBeTruthy()
    expect($registry.get('workflowAction', 'run_agent')).toBeTruthy()
    expect(
      $registry.get('databaseWorkflowActionType', 'run_agent')
    ).toBeTruthy()
  })
})
