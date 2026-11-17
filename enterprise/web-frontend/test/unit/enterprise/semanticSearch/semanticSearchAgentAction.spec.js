import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import AgentActionsSection from '@baserow/modules/agent/components/configuration/AgentActionsSection'
import AgentServicePicker from '@baserow/modules/agent/components/configuration/AgentServicePicker'
import AgentActionCard from '@baserow/modules/agent/components/configuration/AgentActionCard'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { actionFieldLabel } from '@baserow/modules/agent/utils/actionLabels'
import {
  agentData,
  completeConfiguration,
  workspace,
} from '@baserow/test/unit/agent/helpers'

const TYPE = 'local_baserow_semantic_search'
const QUERY_INPUT_ID = '11111111-1111-4111-8111-111111111111'
const t = (key) => `t:${key}`

const searchAction = (service = {}) => ({
  id: 1,
  type: TYPE,
  name: 'semantic_search',
  description: 'Search the table by meaning.',
  enabled: true,
  ask_first: false,
  inputs: [
    {
      id: QUERY_INPUT_ID,
      name: 'query',
      type: 'string',
      description: 'What to look for.',
      required: true,
    },
  ],
  service: {
    id: 20,
    type: TYPE,
    integration_id: null,
    table_id: null,
    view_id: null,
    search_query: {
      formula: `get('tool_input.${QUERY_INPUT_ID}')`,
      mode: 'simple',
      version: '0.1',
    },
    max_results: 10,
    min_similarity: null,
    search_all_fields: true,
    search_field_ids: [],
    include_all_fields: true,
    included_field_ids: [],
    filters: [],
    filter_groups: [],
    filter_type: 'AND',
    ...service,
  },
  errors: { integration_id: 'required', table_id: 'required' },
})

const integration = {
  id: 5,
  type: 'local_baserow',
  name: 'Local Baserow',
  application_id: 10,
  context_data: {
    databases: [
      { id: 7, name: 'Support', tables: [{ id: 8, name: 'Articles' }] },
    ],
  },
}

describe('Semantic search agent action', () => {
  let testApp, presenter
  beforeEach(async () => {
    testApp = new TestApp()
    presenter = testApp.getRegistry().get('toolPresentation', TYPE)
    await testApp.store.dispatch('workspace/forceCreate', clone(workspace))
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  test('a call shows its table, query and maximum results, in that order', () => {
    const shown = presenter.getInput(
      {
        input: {
          values: { max_results: 10, search_query: 'cake', table: 'Articles' },
        },
      },
      t
    )
    expect(Object.entries(shown.values)).toEqual([
      ['t:localBaserowTableSelector.tableFieldLabel', 'Articles'],
      ['t:localBaserowSemanticSearchForm.searchQuery', 'cake'],
      ['t:localBaserowSemanticSearchForm.maxResults', 10],
    ])
    expect(presenter.getActivity({ status: STEP_STATUS.RUNNING }, t)).toBe(
      't:agentSemanticSearch.toolRunning'
    )
    expect(presenter.getActivity({ status: STEP_STATUS.DONE }, t)).toBe(
      't:agentSemanticSearch.toolDone'
    )
  })

  test('configuration errors name the fields the editor shows', () => {
    const registry = testApp.getRegistry()
    expect(
      ['integration_id', 'table_id', 'filters'].map((field) =>
        actionFieldLabel(registry, TYPE, field, t)
      )
    ).toEqual([
      't:localBaserowServiceForm.integrationDropdownLabel',
      't:localBaserowTableSelector.tableFieldLabel',
      't:agentSemanticSearch.filters',
    ])
  })

  test('the card picks the integration first, then hands the form its databases', async () => {
    const agent = await testApp.store.dispatch(
      'application/forceCreate',
      clone(agentData)
    )
    testApp.mock
      .onGet('application/10/integrations/')
      .reply(200, [clone(integration)])
    testApp.mock
      .onGet('/agent/10/actions/')
      .reply(200, [searchAction(), searchAction({ integration_id: 5 })])
    const wrapper = await testApp.mount(AgentActionsSection, {
      props: {
        editable: true,
        configuration: completeConfiguration({
          available_action_types: [TYPE],
        }),
      },
      global: { provide: { agentApplication: ref(agent) } },
    })
    await flushPromises()
    for (const toggle of wrapper.findAll('.agent-action-card__toggle'))
      await toggle.trigger('click')

    const [unconfigured, configured] = wrapper.findAll('.agent-action-card')
    for (const card of [unconfigured, configured])
      expect(card.text()).toContain(
        'localBaserowServiceForm.integrationDropdownLabel'
      )
    expect(
      unconfigured
        .findComponent({ name: 'LocalBaserowSemanticSearchServiceForm' })
        .exists()
    ).toBe(false)
    const form = configured.findComponent({
      name: 'LocalBaserowSemanticSearchServiceForm',
    })
    expect(form.props('databases')).toEqual(integration.context_data.databases)
  })

  const mountCard = async (available) => {
    testApp.store.commit('settings/SET_SETTINGS', {
      semantic_search: { available },
    })
    const agent = await testApp.store.dispatch(
      'application/forceCreate',
      clone(agentData)
    )
    return testApp.mount(AgentActionCard, {
      props: {
        action: searchAction({ integration_id: 5 }),
        workspace,
        editable: true,
        expanded: true,
      },
      global: { provide: { agentApplication: ref(agent) } },
    })
  }

  test('an unlicensed search keeps its switch and name, and its settings open the upgrade modal', async () => {
    const card = await mountCard(true)
    const modal = card.getComponent(PaidFeaturesModal)
    const opened = vi.spyOn(modal.vm.$refs.modal, 'show')
    const enabled = card.get('[role="switch"]')

    expect(enabled.attributes('aria-checked')).toBe('true')
    expect(enabled.classes()).toContain('agent-action-card__switch--locked')
    expect(card.find('.agent-action-card__settings [inert]').exists()).toBe(
      true
    )
    await enabled.trigger('click')
    await card.get('.agent-action-card__body input').setValue('find_articles')
    await card.get('.agent-action-card__lock').trigger('click')
    await card.get('.agent-action-card__settings').trigger('click')
    expect(opened).toHaveBeenCalledTimes(2)
    expect(modal.vm.selectedType).toBe('semantic_search')
    expect(card.emitted('update')).toEqual([
      [{ enabled: false }],
      [{ name: 'find_articles' }],
    ])
    expect(card.text()).toContain('agent.deleteAction')
  })

  test("a search the instance can't run is read-only without an upgrade offer", async () => {
    const card = await mountCard(false)
    expect(card.find('.agent-action-card__settings [inert]').exists()).toBe(
      true
    )
    expect(card.find('.agent-action-card__lock').exists()).toBe(false)
    expect(card.findComponent(PaidFeaturesModal).exists()).toBe(false)
  })

  test("the picker keeps a search the instance can't run disabled and open", async () => {
    testApp.store.commit('settings/SET_SETTINGS', {
      semantic_search: { available: false },
    })
    const picker = await testApp.mount(AgentServicePicker, {
      props: {
        searchPlaceholder: '',
        emptyText: '',
        availableTypes: [TYPE],
        workspace,
      },
    })
    picker.vm.toggle(document.body)
    await flushPromises()
    const hidden = vi.spyOn(picker.vm.$refs.context, 'hide')
    const item = picker.get('.grouped-menu__actions .menu-list__item-button')
    expect(item.find('.deactivated-label.iconoir-lock').exists()).toBe(false)
    await item.trigger('click')
    expect(hidden).not.toHaveBeenCalled()
    expect(picker.emitted('select')).toBeUndefined()
  })
})
