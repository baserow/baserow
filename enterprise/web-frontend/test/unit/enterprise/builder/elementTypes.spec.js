import EnterpriseFeaturesObject from '@baserow_enterprise/features'
import GraphElementForm from '@baserow_enterprise/builder/components/elements/GraphElementForm'

describe('Enterprise builder element types', () => {
  test('file input deactivation checks tolerate a missing workspace', () => {
    const testApp = useNuxtApp()
    const elementType = testApp.$registry.get('element', 'input_file')

    expect(elementType.isDeactivatedReason({ workspace: undefined })).toBeNull()
    expect(elementType.getDeactivatedClickModal({ workspace: undefined })).toBe(
      null
    )
  })

  test('graph element feature is included in enterprise licenses', () => {
    const testApp = useNuxtApp()

    for (const licenseType of [
      testApp.$registry.get('license', 'enterprise_without_support'),
      testApp.$registry.get('license', 'enterprise'),
    ]) {
      expect(licenseType.getFeatures()).toContain(
        EnterpriseFeaturesObject.BUILDER_GRAPH_ELEMENT
      )
    }
  })

  test('graph element defaults use formula series', () => {
    const testApp = useNuxtApp()
    const elementType = testApp.$registry.get('element', 'graph')

    expect(elementType.getDefaultValues({}, {})).toStrictEqual({
      labels: "'label 1,label 2,label 3'",
      series: [
        {
          label: "'Series 1'",
          values: "'10,20,30'",
          color: 'primary',
          chart_type: 'BAR',
        },
      ],
    })
  })

  test('graph element form uses generic series headers', () => {
    expect(
      GraphElementForm.methods.getSeriesTitle.call(
        {
          $t(key, values) {
            return `${key} ${values.number}`
          },
        },
        1
      )
    ).toBe('graphElementForm.series 2')
  })

  test('graph element form accepts theme overrides', () => {
    const data = GraphElementForm.data()

    expect(data.allowedValues).toContain('styles')
    expect(data.values.styles).toStrictEqual({})
  })

  test('graph element form ignores non-series ids when ordering series', () => {
    const form = {
      values: {
        series: [
          {
            label: "'First'",
            values: "'1'",
            color: 'primary',
            chart_type: 'BAR',
          },
          {
            label: "'Second'",
            values: "'2'",
            color: 'warning',
            chart_type: 'LINE',
          },
        ],
      },
      seriesIds: ['first', 'second'],
    }

    GraphElementForm.methods.orderSeries.call(form, [
      undefined,
      'second',
      'first',
    ])

    expect(form.values.series).toStrictEqual([
      {
        label: "'Second'",
        values: "'2'",
        color: 'warning',
        chart_type: 'LINE',
      },
      { label: "'First'", values: "'1'", color: 'primary', chart_type: 'BAR' },
    ])
    expect(form.seriesIds).toStrictEqual(['second', 'first'])
  })
})

describe('Enterprise automation and workflow action types', () => {
  test('code and xls deactivation modal checks tolerate a missing workspace', () => {
    const testApp = useNuxtApp()
    const codeNodeType = testApp.$registry.get('node', 'code')
    const xlsNodeType = testApp.$registry.get('node', 'xls_file_reader')
    const codeWorkflowActionType = testApp.$registry.get(
      'workflowAction',
      'code'
    )
    const xlsWorkflowActionType = testApp.$registry.get(
      'workflowAction',
      'xls_file_reader'
    )

    for (const type of [
      codeNodeType,
      xlsNodeType,
      codeWorkflowActionType,
      xlsWorkflowActionType,
    ]) {
      expect(type.isDeactivatedReason({ workspace: undefined })).toBeNull()
      expect(type.getDeactivatedClickModal({ workspace: undefined })).toBeNull()
    }
  })
})
