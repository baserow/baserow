import { CoreWaitActionNodeType } from '@baserow/modules/automation/nodeTypes'
import { CoreWaitServiceType } from '@baserow/modules/integrations/core/serviceTypes'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('CoreWaitActionNodeType', () => {
  const englishAliases = 'delay, sleep, pause, timer'
  const makeNodeType = ({ serviceType = {} } = {}) =>
    new CoreWaitActionNodeType({
      app: {
        $i18n: {
          t: (key) => (key === 'nodeType.waitAliases' ? englishAliases : key),
        },
        $registry: { get: () => serviceType },
      },
    })

  test('getType is wait', () => {
    expect(CoreWaitActionNodeType.getType()).toBe('wait')
  })

  test('is a workflow action with an output, not a utility node', () => {
    const nodeType = makeNodeType()
    expect(nodeType.isWorkflowAction).toBe(true)
    expect(nodeType.isUtilityNode).toBeUndefined()
  })

  test('name comes from the i18n label', () => {
    expect(makeNodeType().name).toBe('nodeType.waitNodeLabel')
  })

  test('aliases are the terms of the locale string', () => {
    expect(makeNodeType().aliases).toEqual(['delay', 'sleep', 'pause', 'timer'])
  })

  test('description comes from the service type', () => {
    const nodeType = makeNodeType({
      serviceType: { description: 'Pauses the workflow' },
    })
    expect(nodeType.description).toBe('Pauses the workflow')
  })

  describe('registration', () => {
    let testApp = null

    beforeEach(() => {
      testApp = new TestApp()
    })

    afterEach(async () => {
      await testApp.afterEach()
    })

    test('the wait node type is registered', () => {
      const nodeType = testApp.getRegistry().get('node', 'wait')
      expect(nodeType.constructor.getType()).toBe('wait')
    })

    test('the wait node type resolves the registered wait service type', () => {
      const nodeType = testApp.getRegistry().get('node', 'wait')
      const serviceType = testApp.getRegistry().get('service', 'wait')
      expect(serviceType.constructor.getType()).toBe(
        CoreWaitServiceType.getType()
      )
      expect(nodeType.serviceType).toBe(serviceType)
    })
  })
})
