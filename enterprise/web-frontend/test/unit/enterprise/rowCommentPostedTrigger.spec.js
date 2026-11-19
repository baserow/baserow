import { TestApp } from '@baserow/test/helpers/testApp'
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

  test('the agent checkbox follows the run-as identity and disables when it is cleared', async () => {
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
})
