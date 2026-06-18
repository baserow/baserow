import EnterpriseFeaturesObject from '@baserow_enterprise/features'
import GraphElementForm from '@baserow_enterprise/builder/components/elements/GraphElementForm'

describe('Enterprise builder element types', () => {
  describe('Auth form error message', () => {
    const getAuthFormErrorMessage = (
      authProviders,
      applicationContext = {}
    ) => {
      const testApp = useNuxtApp()
      const elementType = testApp.$registry.get('element', 'auth_form')
      const builder = {
        id: 1,
        pages: [{ id: 1, workflowActions: [] }],
        user_sources: [
          {
            id: 1,
            type: 'local_baserow',
            email_field_id: 1,
            name_field_id: 2,
            auth_providers: authProviders,
          },
        ],
      }

      return elementType.getErrorMessage(
        { id: 1, page_id: 1, user_source_id: 1 },
        { builder, ...applicationContext }
      )
    }

    test.each([[null], [undefined]])(
      'reports an error when its only password provider has a %s password field',
      (passwordFieldId) => {
        expect(
          getAuthFormErrorMessage([
            {
              type: 'local_baserow_password',
              password_field_id: passwordFieldId,
            },
          ])
        ).toBe('elementType.errorUserSourceHasNoLoginOption')
      }
    )

    test('accepts a configured local password provider', () => {
      expect(
        getAuthFormErrorMessage([
          {
            type: 'local_baserow_password',
            password_field_id: 3,
          },
        ])
      ).toBeNull()
    })

    test('accepts a configured password provider with a redacted field publicly', () => {
      expect(
        getAuthFormErrorMessage(
          [
            {
              type: 'local_baserow_password',
              password_field_id: undefined,
              is_configured: true,
            },
          ],
          { mode: 'public' }
        )
      ).toBeNull()
    })

    test('reports an error for an unconfigured password provider publicly', () => {
      expect(
        getAuthFormErrorMessage(
          [
            {
              type: 'local_baserow_password',
              password_field_id: undefined,
              is_configured: false,
            },
          ],
          { mode: 'public' }
        )
      ).toBe('elementType.errorUserSourceHasNoLoginOption')
    })

    test.each([
      ['SAML', { type: 'saml', metadata: '<EntityDescriptor />' }],
      [
        'OpenID Connect',
        { type: 'openid_connect', base_url: 'https://idp.example' },
      ],
    ])('accepts a configured %s provider', (_providerName, authProvider) => {
      expect(getAuthFormErrorMessage([authProvider])).toBeNull()
    })

    test('accepts a configured SAML provider alongside an invalid password provider', () => {
      expect(
        getAuthFormErrorMessage([
          {
            type: 'local_baserow_password',
            password_field_id: null,
          },
          {
            type: 'saml',
            metadata: '<EntityDescriptor />',
          },
        ])
      ).toBeNull()
    })

    test('reports an error when the user source has no providers', () => {
      expect(getAuthFormErrorMessage([])).toBe(
        'elementType.errorUserSourceHasNoLoginOption'
      )
    })

    test('uses the public configuration state when its password field is redacted', () => {
      const appAuthProviderType = useNuxtApp().$registry.get(
        'appAuthProvider',
        'local_baserow_password'
      )

      expect(
        appAuthProviderType.isConfigured({ password_field_id: null })
      ).toBe(false)
      expect(
        appAuthProviderType.isConfigured({ password_field_id: undefined })
      ).toBe(false)
      expect(appAuthProviderType.isConfigured({ password_field_id: 3 })).toBe(
        true
      )
      expect(
        appAuthProviderType.isConfigured({
          password_field_id: undefined,
          is_configured: true,
        })
      ).toBe(true)
      expect(
        appAuthProviderType.isConfigured({
          password_field_id: undefined,
          is_configured: false,
        })
      ).toBe(false)
      expect(
        appAuthProviderType.getLoginOptions({
          password_field_id: undefined,
          is_configured: true,
        })
      ).toEqual({})
      expect(
        appAuthProviderType.getLoginOptions({
          password_field_id: undefined,
          is_configured: false,
        })
      ).toBeNull()
    })
  })

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
