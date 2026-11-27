import { AutomaticSnapshotsPaidFeature } from '@baserow_enterprise/paidFeatures'
import { getPaidFeaturesByPlan } from '@baserow_premium/paidFeatures'

describe('AutomaticSnapshotsPaidFeature', () => {
  const createFeature = () =>
    new AutomaticSnapshotsPaidFeature({
      app: { $i18n: { t: (key) => key } },
    })

  test('is an Advanced feature', () => {
    const feature = createFeature()

    expect(AutomaticSnapshotsPaidFeature.getType()).toBe('automatic_snapshots')
    expect(feature.getPlan()).toBe('Advanced')
    expect(feature.getName()).toBe('enterpriseFeatures.automaticSnapshots')
  })

  test('is listed with the Advanced paid features', () => {
    const feature = createFeature()
    const registry = {
      getAll: () => ({ [AutomaticSnapshotsPaidFeature.getType()]: feature }),
    }

    expect(getPaidFeaturesByPlan(registry)).toEqual({ Advanced: [feature] })
  })
})
