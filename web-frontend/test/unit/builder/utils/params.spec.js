import { pathParametersInError } from '@baserow/modules/builder/utils/params'

describe('Builder parameter util tests', () => {
  describe('pathParametersInError', () => {
    test('should return false when element is not a page navigation', () => {
      const element = {
        navigation_type: 'link',
        navigate_to_page_id: 1,
      }
      const pages = [
        { id: 1, path_params: [] },
        { id: 2, path_params: [] },
      ]

      const result = pathParametersInError(element, pages)
      expect(result).toBe(false)
    })

    test('should return false when destinationPage is not found', () => {
      const element = {
        navigation_type: 'page',
        navigate_to_page_id: 3,
      }
      const pages = [{ id: 1, path_params: [] }]

      const result = pathParametersInError(element, pages)
      expect(result).toBe(false)
    })

    test('should return false when page parameters and destinationPage path parameters match', () => {
      const element = {
        navigation_type: 'page',
        navigate_to_page_id: 1,
        page_parameters: [
          { name: 'param1', value: '10' },
          { name: 'param2', value: 'abc' },
        ],
      }
      const pages = [
        {
          id: 1,
          path_params: [
            { name: 'param1', type: 'numeric' },
            { name: 'param2', type: 'text' },
          ],
        },
      ]

      const result = pathParametersInError(element, pages)
      expect(result).toBe(false)
    })

    test('should return true when destinationPage path parameters length does not match page parameters length', () => {
      const element = {
        navigation_type: 'page',
        navigate_to_page_id: 1,
        page_parameters: [
          { name: 'param1', value: '10' },
          { name: 'param2', value: 'abc' },
        ],
      }
      const pages = [
        { id: 1, path_params: [{ name: 'param1', type: 'numeric' }] },
      ]

      const result = pathParametersInError(element, pages)
      expect(result).toBe(true)
    })

    test('should return true when page parameter name does not match destinationPage path parameters', () => {
      const element = {
        navigation_type: 'page',
        navigate_to_page_id: 1,
        page_parameters: [
          { name: 'param1', value: '10' },
          { name: 'param3', value: 'abc' },
        ],
      }

      const pages = [
        {
          id: 1,
          path_params: [
            { name: 'param1', type: 'numeric' },
            { name: 'param2', type: 'text' },
          ],
        },
      ]

      const result = pathParametersInError(element, pages)
      expect(result).toBe(true)
    })
  })
})
