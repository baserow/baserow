import { resolveFormula } from '@baserow/modules/core/formula'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'

describe('resolveElementUrl tests', () => {
  test('Should return empty resolvedContext with page navigation type where page is not found.', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 42,
    }
    const builder = { pages: [{ id: 1 }] }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('')
  })
  test('Should return resolvedContext with page navigation type where page is found and has no params.', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 1,
      page_parameters: [],
    }
    const builder = {
      id: 123,
      pages: [{ id: 1, path: '/contact-us/', path_params: [] }],
    }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('/builder/123/preview/contact-us/')
  })
  test('Should return resolvedContext with page navigation type where page is found and has params.', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 1,
      page_parameters: [{ name: 'id', value: { formula: "'10'" } }],
    }
    const builder = {
      id: 123,
      pages: [
        {
          id: 1,
          path: '/product/:id/',
          path_params: [{ name: 'id', type: 'numeric' }],
        },
      ],
    }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('/builder/123/preview/product/10/')
  })
  test('Should return resolvedContext for external custom navigation type.', () => {
    const element = {
      navigation_type: 'custom',
      navigate_to_url: { formula: "'https://baserow.io'" },
    }
    const builder = { pages: [] }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('https://baserow.io')
  })
  test('Should return resolvedContext for internal custom navigation type.', () => {
    const element = {
      navigation_type: 'custom',
      navigate_to_url: { formula: "'/contact/'" },
    }
    const builder = { id: 123, pages: [] }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('/builder/123/preview/contact/')
  })
  test('Should return resolvedContext and ignore element page params when destination page params are removed', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 1,
      page_parameters: [{ name: 'id', value: { formula: '"10"' } }],
    }
    const builder = {
      id: 123,
      pages: [{ id: 1, path: '/products/', path_params: [] }], // Page parameters have been removed
    }
    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('/builder/123/preview/products/')
  })
})
