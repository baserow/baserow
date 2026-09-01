import { TestApp } from '@baserow/test/helpers/testApp'

describe('Builder collection field types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  describe('LinkCollectionFieldType getErrorMessage', () => {
    test('is in error when custom navigation URL is missing', () => {
      const fieldType = testApp.getRegistry().get('collectionField', 'link')
      const builder = { id: 1, pages: [] }
      const field = {
        type: 'link',
        link_name: { formula: "'Foo'" },
        navigation_type: 'custom',
        navigate_to_url: { formula: '' },
      }

      expect(fieldType.isInError({ field, builder })).toBe(true)
      expect(fieldType.getErrorMessage({ field, builder })).toBe(
        'elementType.errorNavigationUrlMissing'
      )

      // Once a custom URL formula is provided, the field is no longer in error.
      field.navigate_to_url = { formula: "'https://baserow.io'" }

      expect(fieldType.isInError({ field, builder })).toBe(false)
    })

    test('is in error when page navigation has no destination page', () => {
      const fieldType = testApp.getRegistry().get('collectionField', 'link')
      const builder = { id: 1, pages: [] }
      const field = {
        type: 'link',
        link_name: { formula: "'Foo'" },
        navigation_type: 'page',
        navigate_to_page_id: '',
      }

      expect(fieldType.isInError({ field, builder })).toBe(true)
      expect(fieldType.getErrorMessage({ field, builder })).toBe(
        'elementType.errorNavigateToPageMissing'
      )
    })

    test('is in error when a required page parameter is empty', () => {
      const fieldType = testApp.getRegistry().get('collectionField', 'link')
      const builder = {
        id: 1,
        pages: [
          {
            id: 1,
            shared: false,
            order: 1,
            path: '/',
            path_params: [],
          },
          {
            id: 2,
            shared: false,
            order: 2,
            path: '/details/:id',
            path_params: [{ name: 'id', type: 'numeric' }],
          },
        ],
      }
      const field = {
        type: 'link',
        link_name: { formula: "'Foo'" },
        navigation_type: 'page',
        navigate_to_page_id: 2,
        page_parameters: [{ name: 'id', value: { formula: '' } }],
      }

      expect(fieldType.isInError({ field, builder })).toBe(true)
      expect(fieldType.getErrorMessage({ field, builder })).toBe(
        'elementType.errorPageParameterInError'
      )

      // Once the page parameter has a value, the field is no longer in error.
      field.page_parameters = [{ name: 'id', value: { formula: "'10'" } }]

      expect(fieldType.isInError({ field, builder })).toBe(false)
    })
  })

  describe('ButtonCollectionFieldType getErrorMessage', () => {
    test('requires an action for its own click event', () => {
      const fieldType = testApp.getRegistry().get('collectionField', 'button')
      const tableElementType = testApp.getRegistry().get('element', 'table')
      const buttonField = { type: 'button', uid: 'first-button' }
      const otherButtonField = { type: 'button', uid: 'second-button' }
      const page = {
        id: 1,
        workflowActions: [
          {
            element_id: 50,
            event: 'second-button_click',
            order: 1,
            type: 'notification',
          },
        ],
      }
      const element = {
        id: 50,
        type: 'table',
        page_id: page.id,
        fields: [buttonField, otherButtonField],
      }
      const builder = { id: 1, pages: [page] }

      expect(
        fieldType.getErrorMessage({ field: buttonField, element, builder })
      ).toBe('elementType.errorNoWorkflowAction')
      expect(tableElementType.getErrorMessage(element, { builder })).toBe(
        'elementType.errorCollectionFieldInError'
      )

      page.workflowActions.push({
        element_id: element.id,
        event: 'first-button_click',
        order: 2,
        type: 'notification',
      })
      expect(
        fieldType.getErrorMessage({ field: buttonField, element, builder })
      ).toBeNull()
    })
  })
})
