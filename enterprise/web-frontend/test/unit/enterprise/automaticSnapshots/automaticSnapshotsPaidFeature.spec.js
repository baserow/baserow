import { AutomaticSnapshotsPaidFeature } from '@baserow_enterprise/paidFeatures'
import { getPaidFeaturesByPlan } from '@baserow_premium/paidFeatures'

describe('AutomaticSnapshotsPaidFeature', () => {
  const createFeature = (featureFlagIsEnabled) =>
    new AutomaticSnapshotsPaidFeature({
      app: {
        $featureFlagIsEnabled: featureFlagIsEnabled,
        $i18n: { t: (key) => key },
      },
    })

  test('is an Advanced feature', () => {
    const feature = createFeature(() => true)

    expect(AutomaticSnapshotsPaidFeature.getType()).toBe('automatic_snapshots')
    expect(feature.getPlan()).toBe('Advanced')
    expect(feature.getName()).toBe('enterpriseFeatures.automaticSnapshots')
  })

  test('is only listed with its feature flag', () => {
    const featureFlagIsEnabled = vi.fn().mockReturnValue(false)

    expect(createFeature(featureFlagIsEnabled).isEnabled()).toBe(false)
    expect(featureFlagIsEnabled).toHaveBeenCalledWith('automatic_snapshots')
  })

  test('is left out of the paid features by plan without its feature flag', () => {
    const registryWith = (feature) => ({
      getAll: () => ({ [AutomaticSnapshotsPaidFeature.getType()]: feature }),
    })

    expect(
      getPaidFeaturesByPlan(registryWith(createFeature(() => false)))
    ).toEqual({})
    const enabled = createFeature(() => true)
    expect(getPaidFeaturesByPlan(registryWith(enabled))).toEqual({
      Advanced: [enabled],
    })
  })
})
