import { describe, expect, test } from 'vitest'

import {
  getCleanCallbackLocation,
  getAuthProviderCallback,
  getAuthProviderCallbackParamNames,
  getAuthProviderCallbackUrl,
} from '@baserow/modules/builder/middleware/userSourceAuthProviderCallback'

const samlProviderType = {
  getAuthProviderCallbackQueryParamNames: (url) =>
    [...url.searchParams.keys()].filter((name) =>
      name.startsWith('user_source_saml_token__')
    ),
  getAuthProviderCallback(userSource, url) {
    const queryParamName = `user_source_saml_token__${userSource.id}`
    const values = url.searchParams.getAll(queryParamName)
    return values.length === 1 && values[0]
      ? {
          sourceId: userSource.id,
          token: values[0],
          queryParamNames: [queryParamName],
        }
      : null
  },
}

const registry = {
  get() {
    return samlProviderType
  },
  getAll() {
    return {
      saml: samlProviderType,
      oidc: {
        getAuthProviderCallbackQueryParamNames: (url) =>
          [...url.searchParams.keys()].filter((name) =>
            name.startsWith('user_source_oidc_token__')
          ),
      },
    }
  },
}

const arbitraryProviderType = {
  getAuthProviderCallbackQueryParamNames: (url) =>
    url.searchParams.has('custom_callback') ? ['custom_callback'] : [],
  getAuthProviderCallback(userSource, url) {
    const values = url.searchParams.getAll('custom_callback')
    return values.length === 1 && values[0]
      ? {
          sourceId: userSource.id,
          token: values[0],
          queryParamNames: ['custom_callback'],
        }
      : null
  },
}

const arbitraryRegistry = {
  get() {
    return arbitraryProviderType
  },
  getAll() {
    return { custom: arbitraryProviderType }
  },
}

const arbitraryBuilder = {
  user_sources: [
    {
      id: 15,
      auth_providers: [{ type: 'custom' }],
    },
  ],
}

const builder = {
  user_sources: [
    {
      id: 12,
      auth_providers: [{ type: 'saml' }],
    },
  ],
}

describe('Builder user source auth provider callback middleware', () => {
  test('uses the current router target instead of a stale request URL', () => {
    const requestUrl = new URL(
      'https://site.example/page?user_source_saml_token__12=refresh'
    )
    const callbackUrl = getAuthProviderCallbackUrl(
      { fullPath: '/page' },
      requestUrl
    )

    expect(callbackUrl.toString()).toBe('https://site.example/page')
  })

  test('delegates exactly one callback to its configured provider', () => {
    expect(
      getAuthProviderCallback(
        new URL('https://site.example/?user_source_saml_token__12=refresh'),
        builder,
        registry
      )
    ).toEqual({
      sourceId: 12,
      token: 'refresh',
      queryParamNames: ['user_source_saml_token__12'],
    })
    expect(
      getAuthProviderCallback(
        new URL(
          'https://site.example/?user_source_saml_token__12=a&user_source_saml_token__12=b'
        ),
        builder,
        registry
      )
    ).toBeNull()
    expect(
      getAuthProviderCallback(
        new URL('https://site.example/?user_source_unknown_opaque=value'),
        builder,
        registry
      )
    ).toBeNull()
    expect(
      getAuthProviderCallback(
        new URL(
          'https://site.example/?user_source_saml_token__12=refresh&user_source_unknown_opaque=value'
        ),
        builder,
        registry
      )
    ).toEqual({
      sourceId: 12,
      token: 'refresh',
      queryParamNames: ['user_source_saml_token__12'],
    })
  })

  test('ignores parameters not claimed by a provider', () => {
    const url = new URL(
      'https://site.example/?user_source_unknown_token__9=secret'
    )

    expect(getAuthProviderCallbackParamNames(url, registry)).toEqual([])
    expect(getCleanCallbackLocation(url, registry)).toBe(
      '/?user_source_unknown_token__9=secret'
    )
  })

  test('delegates arbitrary callback parameters to the provider', () => {
    const url = new URL('https://site.example/?custom_callback=refresh')

    expect(getAuthProviderCallbackParamNames(url, arbitraryRegistry)).toEqual([
      'custom_callback',
    ])
    expect(
      getAuthProviderCallback(url, arbitraryBuilder, arbitraryRegistry)
    ).toEqual({
      sourceId: 15,
      token: 'refresh',
      queryParamNames: ['custom_callback'],
    })
    expect(getCleanCallbackLocation(url, arbitraryRegistry)).toBe('/')
  })

  test('removes all callback credentials, including nested next values', () => {
    const url = new URL(
      'https://site.example/page?user_source_saml_token__12=bad&next=%2Ftarget%3Fuser_source_oidc_token__12%3Dnested%26keep%3Dyes&keep=yes'
    )
    expect(getCleanCallbackLocation(url, registry)).toBe(
      '/page?next=%2Ftarget%3Fkeep%3Dyes&keep=yes'
    )
  })

  test('preserves an encoded next value without callback credentials', () => {
    const url = new URL(
      'https://site.example/login?user_source_saml_token__12=refresh&next=%252Fbuilder%252Fpreview%252F2%252Fproducts'
    )

    expect(getCleanCallbackLocation(url, registry)).toBe(
      '/login?next=%252Fbuilder%252Fpreview%252F2%252Fproducts'
    )
  })

  test('removes callback credentials from a double-encoded next value', () => {
    const url = new URL(
      'https://site.example/login?user_source_saml_token__12=refresh&next=%252Ftarget%253Fuser_source_oidc_token__12%253Dnested%2526keep%253Dyes'
    )

    expect(getCleanCallbackLocation(url, registry)).toBe(
      '/login?next=%252Ftarget%253Fkeep%253Dyes'
    )
  })
})
