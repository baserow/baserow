import { ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentTriggerCard from '@baserow/modules/agent/components/configuration/AgentTriggerCard'
import AgentServicePicker from '@baserow/modules/agent/components/configuration/AgentServicePicker'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import WorkflowAddNodeMenu from '@baserow/modules/automation/components/workflow/WorkflowAddNodeMenu'
import LocalBaserowTableSelector from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableSelector'
import en from '@baserow_enterprise/locales/en.json'

const type = 'local_baserow_row_comment_posted'
const databases = [{ id: 7, name: 'Sales', tables: [{ id: 5, name: 'Tasks' }] }]

describe('Row comment posted trigger', () => {
  let testApp, serviceType, t

  beforeEach(async () => {
    const { createI18n } = await vi.importActual('vue-i18n')
    t = createI18n({
      legacy: false,
      locale: 'en',
      messages: { en },
      missingWarn: false,
    }).global.t
    testApp = new TestApp()
    vi.spyOn(testApp.getApp().$i18n, 't').mockImplementation(t)
    serviceType = testApp.getRegistry().get('service', type)
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  const mountForm = (props) =>
    testApp.mount(serviceType.formComponent, {
      global: { mocks: { $t: t } },
      props: {
        serviceType,
        databases,
        service: { table_id: 5, only_when_mentioned: false },
        ...props,
      },
    })

  test('the automation checkbox names the selected integration subject and saves only its setting', async () => {
    const integration = (id, name) => ({
      id,
      authorized_subject: { type: 'auth.User', name },
    })
    const application = {
      type: 'automation',
      integrations: [integration(1, 'Morgan'), integration(2, 'Taylor')],
    }
    const service = {
      integration_id: 1,
      table_id: 5,
      only_when_mentioned: false,
    }
    const wrapper = await mountForm({ application, service })
    expect(wrapper.get('label.checkbox').text()).toBe(
      'Only trigger when Morgan is mentioned'
    )
    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(wrapper.emitted('values-changed').at(-1)).toEqual([
      { only_when_mentioned: true },
    ])
    await wrapper.setProps({
      service: { ...service, only_when_mentioned: true, integration_id: 2 },
    })
    expect(wrapper.get('label.checkbox').text()).toBe(
      'Only trigger when Taylor is mentioned'
    )
    expect(wrapper.get('input[type="checkbox"]').element.checked).toBe(true)
    const table = wrapper.getComponent(LocalBaserowTableSelector)
    expect(table.props('displayViewDropdown')).toBe(false)
    table.vm.$emit('update:modelValue', 12)
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('values-changed').at(-1)[0]).toMatchObject({
      table_id: 12,
    })
  })

  test('the agent checkbox follows the run-as identity and, once it is cleared, can only be unchecked', async () => {
    const wrapper = await mountForm({
      application: { type: 'agent' },
      mentionName: 'Triage agent',
    })
    expect(wrapper.get('label.checkbox').text()).toBe(
      'Only trigger when Triage agent is mentioned'
    )
    await wrapper.setProps({ mentionName: 'Reviewer' })
    expect(wrapper.get('label.checkbox').text()).toBe(
      'Only trigger when Reviewer is mentioned'
    )
    await wrapper.setProps({ mentionName: '' })
    expect(wrapper.get('input[type="checkbox"]').element.disabled).toBe(true)
    expect(wrapper.get('label.checkbox').text()).toBe(
      'Only trigger when mentioned'
    )
    await wrapper.setProps({
      service: { table_id: 5, only_when_mentioned: true },
    })
    const checkbox = wrapper.get('input[type="checkbox"]')
    expect(checkbox.element.disabled).toBe(false)
    await checkbox.setValue(false)
    expect(wrapper.emitted('values-changed').at(-1)).toEqual([
      { only_when_mentioned: false },
    ])
  })

  test('the table field explains a missing comment permission and clears the warning once granted', async () => {
    const application = { type: 'automation', integrations: [] }
    const service = { table_id: 5, context_data: { can_read_comments: false } }
    const wrapper = await mountForm({ application, service })
    const warning =
      'The integration needs permission to read row comments on this table.'
    expect(wrapper.text()).toContain(warning)
    expect(serviceType.getErrorMessage({ service })).toBe(warning)
    await wrapper.setProps({
      service: { ...service, context_data: { can_read_comments: true } },
    })
    expect(wrapper.text()).not.toContain(warning)
  })

  test('the locked automation trigger opens its own Advanced feature explanation', () => {
    const registry = testApp.getRegistry()
    const node = registry.get('node', type)
    const context = { workspace: { id: 1 } }
    const [, props] = node.getDeactivatedClickModal(context)
    const feature = registry.get('paidFeature', props['initial-selected-type'])
    expect(feature.getPlan()).toBe('Advanced')
    expect(feature.getName()).toBe('Row comment is posted')
    expect(feature.getContent()).toContain(
      'Start an automation or agent when someone posts a row comment.'
    )
  })

  test('both hosts offer a single comment, and the agent opens with its author, source and text', () => {
    const registry = testApp.getRegistry()
    const node = registry.get('node', type)
    expect(node.isTrigger).toBe(true)
    expect(node.serviceType).toBe(serviceType)
    expect(serviceType.returnsList({})).toBe(false)
    expect(serviceType.getDefaultName({ table_id: 5 }, { databases })).toBe(
      'Row comment is posted in Tasks'
    )
    const { formula } = registry
      .get('agentTriggerType', type)
      .getDefaultMessage()
    for (const name of ['user_name', 'row_id', 'table_id', 'text']) {
      expect(formula).toContain(`get('trigger.${name}')`)
    }
  })
  test('an unlicensed agent trigger keeps its switch, can be switched off but not on, and its read-only settings open the upgrade modal', async () => {
    const card = await testApp.mount(AgentTriggerCard, {
      props: {
        trigger: {
          id: 1,
          type,
          name: '',
          enabled: true,
          message: { formula: '', mode: 'simple' },
          on_overlap: 'wait',
          batch_size: 20,
          service: { table_id: 5, only_when_mentioned: false },
        },
        workspace: { id: 1 },
        editable: true,
        expanded: true,
        runAsActive: true,
        typeOptions: { form_choices: { databases } },
        availableTypes: [type],
      },
      global: {
        mocks: { $t: t },
        provide: { agentApplication: ref({ id: 10, type: 'agent' }) },
      },
    })
    const modal = card.getComponent(PaidFeaturesModal)
    const opened = vi.spyOn(modal.vm.$refs.modal, 'show')

    expect(card.get('[role="switch"]').attributes('aria-checked')).toBe('true')
    expect(card.findAll('.agent-trigger-card__section[inert]')).toHaveLength(3)
    expect(
      card.get('.agent-trigger-card__name').attributes('readonly')
    ).toBeUndefined()
    expect(
      card.get('.agent-trigger-card__type').attributes('disabled')
    ).toBeUndefined()
    await card.get('[role="switch"]').trigger('click')
    expect(card.emitted('update')).toEqual([[{ enabled: false }]])
    await card.setProps({
      trigger: { ...card.props('trigger'), enabled: false },
    })
    await card.get('[role="switch"]').trigger('click')
    await card.get('.agent-trigger-card__lock').trigger('click')
    await card.get('.agent-trigger-card__body').trigger('click')
    expect(opened).toHaveBeenCalledTimes(3)
    expect(modal.vm.selectedType).toBe('row_comment_trigger')
    expect(card.emitted('update')).toHaveLength(1)
    expect(card.find('.agent-trigger-card__delete').exists()).toBe(true)
  })

  test('the agent picker lists the unlicensed trigger locked and opens its upgrade modal', async () => {
    const picker = await testApp.mount(AgentServicePicker, {
      props: {
        searchPlaceholder: '',
        emptyText: '',
        availableTypes: [type],
        workspace: { id: 1 },
      },
      global: { mocks: { $t: t } },
    })
    picker.vm.toggle(document.body)
    await flushPromises()
    const modal = picker.getComponent(PaidFeaturesModal)
    const opened = vi.spyOn(modal.vm.$refs.modal, 'show')
    const item = picker.get('.grouped-menu__actions .menu-list__item-button')
    expect(item.text()).toContain('Row comment is posted')
    expect(item.find('.deactivated-label.iconoir-lock').exists()).toBe(true)
    await item.trigger('click')
    expect(opened).toHaveBeenCalledOnce()
    expect(picker.emitted('select')).toBeUndefined()
  })

  test('the agent picker stays open on a disabled type without an upgrade modal', async () => {
    vi.spyOn(serviceType, 'getDeactivatedClickModal').mockReturnValue(null)
    const picker = await testApp.mount(AgentServicePicker, {
      props: {
        searchPlaceholder: '',
        emptyText: '',
        availableTypes: [type],
        workspace: { id: 1 },
      },
      global: { mocks: { $t: t } },
    })
    picker.vm.toggle(document.body)
    await flushPromises()
    await picker
      .get('.grouped-menu__actions .menu-list__item-button')
      .trigger('click')
    expect(picker.vm.$refs.context.isOpen()).toBe(true)
    expect(picker.emitted('select')).toBeUndefined()
  })
  test('the automation trigger menu keeps the icon and adds the lock badge', async () => {
    const menu = await testApp.mount(WorkflowAddNodeMenu, {
      props: { onlyTrigger: true },
      global: {
        mocks: { $t: t },
        provide: {
          automation: { id: 1 },
          workflow: { id: 1, nodes: [] },
          workspace: { id: 1 },
        },
      },
    })
    await menu.get('.menu-search__input').setValue('Row comment is posted')
    const item = menu.get('.grouped-menu__actions .menu-list__item-button')
    expect(item.find('.iconoir-chat-bubble').exists()).toBe(true)
    expect(item.find('.deactivated-label.iconoir-lock').exists()).toBe(true)
  })
})
