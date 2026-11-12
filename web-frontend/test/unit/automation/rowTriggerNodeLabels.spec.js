import { readFileSync } from 'fs'
import { resolve } from 'path'
import {
  LocalBaserowRowsCreatedTriggerNodeType,
  LocalBaserowRowsDeletedTriggerNodeType,
  LocalBaserowRowsUpdatedTriggerNodeType,
} from '@baserow/modules/automation/nodeTypes'
import {
  LocalBaserowRowsCreatedTriggerServiceType,
  LocalBaserowRowsDeletedTriggerServiceType,
  LocalBaserowRowsUpdatedTriggerServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'

const readLocale = (module) =>
  JSON.parse(
    readFileSync(
      resolve(process.cwd(), `modules/${module}/locales/en.json`),
      'utf8'
    )
  )
const automation = readLocale('automation')
const integrations = readLocale('integrations')
const en = {
  ...automation,
  serviceType: { ...automation.serviceType, ...integrations.serviceType },
}
const t = (key, values = {}) =>
  key
    .split('.')
    .reduce((messages, part) => messages[part], en)
    .replace(/\{(\w+)\}/g, (placeholder, name) => values[name])

describe('Local Baserow row trigger node labels', () => {
  test('name the table the node watches', () => {
    const serviceTypes = [
      LocalBaserowRowsCreatedTriggerServiceType,
      LocalBaserowRowsUpdatedTriggerServiceType,
      LocalBaserowRowsDeletedTriggerServiceType,
    ]
    const app = {
      $i18n: { t },
      $store: {
        getters: {
          'integration/getIntegrationById': () => ({
            context_data: {
              databases: [{ tables: [{ id: 5, name: 'Orders' }] }],
            },
          }),
        },
      },
      $registry: {
        get: (registry, type) =>
          new (serviceTypes.find(
            (ServiceType) => ServiceType.getType() === type
          ))({ app }),
      },
    }
    const node = { service: { integration_id: 1, table_id: 5 } }

    expect(
      [
        LocalBaserowRowsCreatedTriggerNodeType,
        LocalBaserowRowsUpdatedTriggerNodeType,
        LocalBaserowRowsDeletedTriggerNodeType,
      ].map((NodeType) =>
        new NodeType({ app }).getDefaultLabel({ automation: {}, node })
      )
    ).toEqual([
      'Rows are created in Orders',
      'Rows are updated in Orders',
      'Rows are deleted in Orders',
    ])
  })
})
