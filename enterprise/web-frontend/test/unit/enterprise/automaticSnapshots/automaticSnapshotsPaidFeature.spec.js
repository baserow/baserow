import { AutomaticSnapshotsPaidFeature } from '@baserow_enterprise/paidFeatures'

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
})
