import {
  CheckboxElementType,
  ChoiceElementType,
  ElementType,
  InputTextElementType,
  RecordSelectorElementType,
} from '@baserow/modules/builder/elementTypes'
import { TestApp } from '@baserow/test/helpers/testApp'

import {
  IFRAME_SOURCE_TYPES,
  IMAGE_SOURCE_TYPES,
} from '@baserow/modules/builder/enums'

describe('elementTypes tests', () => {
  const testApp = new TestApp()

  const contextBlankParam = { page: { parameters: { id: '' } } }

  describe('CollectionElementTypeMixin tests', () => {
    test('hasAncestorOfType', () => {
      const page = { id: 123 }
      const elementParent = { id: 456, type: 'column', page_id: page.id }
      const element = {
        id: 789,
        type: 'heading',
        page_id: page.id,
        parent_element_id: elementParent.id,
      }
      page.elementMap = { 456: elementParent, 789: element }
      const elementType = testApp.getRegistry().get('element', element.type)
      expect(elementType.hasAncestorOfType(page, element, 'column')).toBe(true)
      expect(elementType.hasAncestorOfType(page, element, 'repeat')).toBe(false)
    })

    test('hasCollectionAncestor', () => {
      const page = { id: 123 }
      const repeatAncestor = { id: 111, type: 'repeat', page_id: page.id }
      const tableElement = {
        id: 222,
        type: 'table',
        page_id: page.id,
        parent_element_id: repeatAncestor.id,
      }
      page.elementMap = { 111: repeatAncestor, 222: tableElement }
      const repeatElementType = testApp
        .getRegistry()
        .get('element', repeatAncestor.type)
      expect(
        repeatElementType.hasCollectionAncestor(page, repeatAncestor)
      ).toBe(false)
      const tableElementType = testApp
        .getRegistry()
        .get('element', tableElement.type)
      expect(tableElementType.hasCollectionAncestor(page, tableElement)).toBe(
        true
      )
    })

    test('hasSourceOfData', () => {
      const repeatElementType = testApp.getRegistry().get('element', 'repeat')
      expect(repeatElementType.hasSourceOfData({ data_source_id: 1 })).toBe(
        true
      )
      expect(
        repeatElementType.hasSourceOfData({ schema_property: 'field_1' })
      ).toBe(true)
      expect(
        repeatElementType.hasSourceOfData({
          data_source_id: null,
          schema_property: null,
        })
      ).toBe(false)
    })
  })

  describe('elementType getDisplayName permutation tests', () => {
    test('ElementType returns the name by default', () => {
      const elementType = new ElementType()
      expect(elementType.getDisplayName({}, {})).toBe(null)
    })
    test('ColumnElementType returns the name by default', () => {
      const elementType = testApp.getRegistry().get('element', 'column')
      expect(elementType.getDisplayName({}, {})).toBe('elementType.column')
    })
    test('InputTextElementType label and default_value variations', () => {
      const elementType = testApp.getRegistry().get('element', 'input_text')
      expect(elementType.getDisplayName({ label: "'First name'" }, {})).toBe(
        'First name'
      )
      expect(
        elementType.getDisplayName(
          { default_value: "'Enter a first name'" },
          {}
        )
      ).toBe('Enter a first name')
      expect(
        elementType.getDisplayName(
          { placeholder: "'Choose a first name...'" },
          {}
        )
      ).toBe('Choose a first name...')
      // If a formula resolves to a blank string, fallback to the name.
      expect(
        elementType.getDisplayName(
          { label: "get('page_parameter.id')" },
          contextBlankParam
        )
      ).toBe(elementType.name)
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
    test('ChoiceElementType label, default_value & placeholder variations', () => {
      const elementType = testApp.getRegistry().get('element', 'choice')
      expect(elementType.getDisplayName({ label: "'Animals'" }, {})).toBe(
        'Animals'
      )
      expect(elementType.getDisplayName({ default_value: "'Horse'" }, {})).toBe(
        'Horse'
      )
      expect(
        elementType.getDisplayName({ default_value: "'Choose an animal'" }, {})
      ).toBe('Choose an animal')
      // If a formula resolves to a blank string, fallback to the name.
      expect(
        elementType.getDisplayName(
          { label: "get('page_parameter.id')" },
          contextBlankParam
        )
      ).toBe(elementType.name)
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
    test('CheckboxElementType with and without a label to use', () => {
      const elementType = testApp.getRegistry().get('element', 'checkbox')
      expect(elementType.getDisplayName({ label: "'Active'" }, {})).toBe(
        'Active'
      )
      // If a formula resolves to a blank string, fallback to the name.
      expect(
        elementType.getDisplayName(
          { label: "get('page_parameter.id')" },
          contextBlankParam
        )
      ).toBe(elementType.name)
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
    test('HeadingElementType with and without a value to use', () => {
      const elementType = testApp.getRegistry().get('element', 'heading')
      expect(elementType.getDisplayName({ value: "'A heading'" }, {})).toBe(
        'A heading'
      )
      // If a formula resolves to a blank string, fallback to the name.
      expect(
        elementType.getDisplayName(
          { value: "get('page_parameter.id')" },
          contextBlankParam
        )
      ).toBe(elementType.name)
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
    test('TextElementType with and without a value to use', () => {
      const elementType = testApp.getRegistry().get('element', 'text')
      expect(elementType.getDisplayName({ value: "'Some text'" }, {})).toBe(
        'Some text'
      )
      // If a formula resolves to a blank string, fallback to the name.
      expect(
        elementType.getDisplayName(
          { value: "get('page_parameter.id')" },
          contextBlankParam
        )
      ).toBe(elementType.name)
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
    test('LinkElementType page and custom URL variations', () => {
      const elementType = testApp.getRegistry().get('element', 'link')
      const applicationContext = {
        builder: {
          pages: [{ id: 1, name: 'Contact Us', shared: false }],
        },
      }
      expect(
        elementType.getDisplayName(
          {
            navigate_to_page_id: 1,
            navigation_type: 'page',
          },
          applicationContext
        )
      ).toBe('elementType.link -> Contact Us')

      // If we were not able to find the page, we fall back to trying for a value.
      expect(
        elementType.getDisplayName(
          {
            value: "'Click me'",
            navigate_to_page_id: 2,
            navigation_type: 'page',
          },
          applicationContext
        )
      ).toBe('Click me')

      // If we were not able to find the page, and there's no value, we fall back to the name.
      expect(
        elementType.getDisplayName(
          {
            navigate_to_page_id: 2,
            navigation_type: 'page',
          },
          applicationContext
        )
      ).toBe(elementType.name)

      expect(
        elementType.getDisplayName(
          {
            navigation_type: 'custom',
            navigate_to_url: "'https://baserow.io'",
            value: "'Link name'",
          },
          applicationContext
        )
      ).toBe('Link name -> https://baserow.io')
    })
    test('ImageElementType with and without alt text to use', () => {
      const elementType = testApp.getRegistry().get('element', 'image')
      expect(
        elementType.getDisplayName({ alt_text: "'Baserow logo'" }, {})
      ).toBe('Baserow logo')
      // If a formula resolves to a blank string, fallback to the name.
      expect(
        elementType.getDisplayName(
          { alt_text: "get('page_parameter.id')" },
          contextBlankParam
        )
      ).toBe(elementType.name)
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
    test('ButtonElementType with and without value to use', () => {
      const elementType = testApp.getRegistry().get('element', 'button')
      expect(elementType.getDisplayName({ value: "'Click me'" }, {})).toBe(
        'Click me'
      )
      // If a formula resolves to a blank string, fallback to the name.
      expect(
        elementType.getDisplayName(
          { value: "get('page_parameter.id')" },
          contextBlankParam
        )
      ).toBe(elementType.name)
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
    test('TableElementType with and without data_source_id to use', () => {
      const elementType = testApp.getRegistry().get('element', 'table')
      const page = {
        id: 1,
        name: 'Contact Us',
        dataSources: [
          { id: 1, type: 'local_baserow_list_rows', name: 'Customers' },
        ],
      }

      const sharedPage = {
        id: 2,
        shared: true,
        name: '__shared__',
        dataSources: [],
      }

      const applicationContext = {
        page,
        builder: { pages: [page, sharedPage] },
      }
      expect(
        elementType.getDisplayName({ data_source_id: 1 }, applicationContext)
      ).toBe('elementType.table - Customers')

      // In the event we don't find the data source.
      expect(
        elementType.getDisplayName({ data_source_id: 2 }, applicationContext)
      ).toBe(elementType.name)

      expect(elementType.getDisplayName({}, applicationContext)).toBe(
        elementType.name
      )
    })
    test('FormContainerElementType returns the name by default', () => {
      const elementType = testApp.getRegistry().get('element', 'form_container')
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
    test('IFrameElementType with and without a url to use', () => {
      const elementType = testApp.getRegistry().get('element', 'iframe')
      expect(
        elementType.getDisplayName(
          { url: "'https://www.youtube.com/watch?v=dQw4w9WgXcQ'" },
          {}
        )
      ).toBe('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
      expect(elementType.getDisplayName({}, {})).toBe(elementType.name)
    })
  })

  describe('elementType form validation tests', () => {
    test('InputTextElementType | required | no value.', () => {
      const elementType = new InputTextElementType()
      expect(elementType.isValid({ required: true }, '')).toBe(false)
    })
    test('InputTextElementType | required | integer | valid value.', () => {
      const elementType = new InputTextElementType()
      expect(
        elementType.isValid({ required: true, validation_type: 'integer' }, 42)
      ).toBe(true)
    })
    test('InputTextElementType | required | integer | invalid value.', () => {
      const elementType = new InputTextElementType()
      expect(
        elementType.isValid(
          { required: true, validation_type: 'integer' },
          'horse'
        )
      ).toBe(false)
    })
    test('InputTextElementType | not required | integer | no value.', () => {
      const elementType = new InputTextElementType()
      expect(
        elementType.isValid({ required: false, validation_type: 'integer' }, '')
      ).toBe(true)
    })
    test('InputTextElementType | required | email | valid value.', () => {
      const elementType = new InputTextElementType()
      expect(
        elementType.isValid(
          { required: true, validation_type: 'email' },
          'peter@baserow.io'
        )
      ).toBe(true)
    })
    test('InputTextElementType | required | email | invalid value.', () => {
      const elementType = new InputTextElementType()
      expect(
        elementType.isValid(
          { required: true, validation_type: 'email' },
          'peterbaserow.io'
        )
      ).toBe(false)
    })
    test('InputTextElementType | not required | email | no value.', () => {
      const elementType = new InputTextElementType()
      expect(
        elementType.isValid({ required: false, validation_type: 'email' }, '')
      ).toBe(true)
    })
    test('InputTextElementType with any value.', () => {
      const elementType = new InputTextElementType()
      expect(elementType.isValid({ validation_type: 'any' }, 42)).toBe(true)
      expect(elementType.isValid({ validation_type: 'any' }, 'horse')).toBe(
        true
      )
      expect(
        elementType.isValid({ validation_type: 'any' }, 'peter@baserow.io')
      ).toBe(true)
    })
    test('CheckboxElementType | required | unchecked.', () => {
      const elementType = new CheckboxElementType()
      expect(elementType.isValid({ required: true }, false)).toBe(false)
    })
    test('CheckboxElementType | required | checked.', () => {
      const elementType = new CheckboxElementType()
      expect(elementType.isValid({ required: true }, true)).toBe(true)
    })
    test('CheckboxElementType | not required | unchecked.', () => {
      const elementType = new CheckboxElementType()
      expect(elementType.isValid({ required: false }, false)).toBe(true)
    })
    test('CheckboxElementType | not required | checked.', () => {
      const elementType = new CheckboxElementType()
      expect(elementType.isValid({ required: false }, true)).toBe(true)
    })
    test('ChoiceElementType | required | no value.', () => {
      const elementType = new ChoiceElementType()
      const element = {
        required: true,
        options: [{ id: 1, value: 'uk', name: 'UK' }],
      }
      expect(elementType.isValid(element, '', {})).toBe(false)
    })
    test('ChoiceElementType | required | blank option.', () => {
      const elementType = new ChoiceElementType()
      const element = {
        required: true,
        options: [
          { id: 1, value: '', name: 'Blank' },
          { id: 2, value: 'uk', name: 'UK' },
        ],
      }
      expect(elementType.isValid(element, '', {})).toBe(true)
    })
    test('ChoiceElementType | required | valid value.', () => {
      const elementType = new ChoiceElementType()
      const element = {
        required: true,
        options: [{ id: 1, value: 'uk', name: 'UK' }],
      }
      expect(elementType.isValid(element, 'uk', {})).toBe(true)
    })
    test('ChoiceElementType | not required | no value.', () => {
      const elementType = new ChoiceElementType()
      const element = {
        required: false,
        options: [{ id: 1, value: 'uk', name: 'UK' }],
      }
      expect(elementType.isValid(element, '', {})).toBe(true)
    })
    test('ChoiceElementType | not required | valid value.', () => {
      const elementType = new ChoiceElementType()
      const element = {
        required: false,
        options: [{ id: 1, value: 'uk', name: 'UK' }],
      }
      expect(elementType.isValid(element, 'uk', {})).toBe(true)
    })
    test('RecordSelectorElementType | required | no value.', () => {
      const elementType = new RecordSelectorElementType()
      const element = { required: true, multiple: false }
      expect(elementType.isValid(element, '', {})).toBe(false)
    })
    test('RecordSelectorType | required | valid value.', () => {
      const app = {
        store: {
          getters: {
            'elementContent/getElementContent'() {
              return [{ id: 1 }, { id: 2 }]
            },
          },
        },
      }
      const elementType = new RecordSelectorElementType({ app })
      const element = { required: true, multiple: false, data_source_id: 1 }
      expect(elementType.isValid(element, 1, {})).toBe(true)
    })
    test('RecordSelectorElementType | not required | no value.', () => {
      const app = {
        store: {
          getters: {
            'elementContent/getElementContent'() {
              return [{ id: 1 }, { id: 2 }]
            },
          },
        },
      }
      const elementType = new RecordSelectorElementType({ app })
      const element = { required: false, multiple: false, data_source_id: 1 }
      expect(elementType.isValid(element, '', {})).toBe(true)
    })
    test('RecordSelectorType | not required | valid value.', () => {
      const app = {
        store: {
          getters: {
            'elementContent/getElementContent'() {
              return [{ id: 1 }, { id: 2 }]
            },
          },
        },
      }
      const elementType = new RecordSelectorElementType({ app })
      const element = { required: false, multiple: false, data_source_id: 1 }
      expect(elementType.isValid(element, 1, {})).toBe(true)
    })
  })

  describe('elementType isDisallowedReason for base elements', () => {
    test("Heading can't be placed on header nor footer if before/after another element", () => {
      const headingElementType = testApp.getRegistry().get('element', 'heading')

      const page = { id: 123 }
      const sharedPage = { id: 124, shared: true }
      const anotherMultiPage = {
        id: 111,
        type: 'header',
        page_id: sharedPage.id,
      }
      page.elementMap = {}
      sharedPage.elementMap = { 111: anotherMultiPage }

      expect(
        headingElementType.isDisallowedReason({
          builder: { id: 1, pages: [sharedPage, page] },
          page: sharedPage,
          parentElement: null,
          beforeElement: anotherMultiPage,
          placeInContainer: null,
          pagePlace: 'header',
        })
      ).toEqual('elementType.notAllowedLocation')

      expect(
        headingElementType.isDisallowedReason({
          builder: { id: 1, pages: [sharedPage, page] },
          page: sharedPage,
          parentElement: null,
          beforeElement: null,
          placeInContainer: null,
          pagePlace: 'footer',
        })
      ).toEqual('elementType.notAllowedLocation')
    })
  })

  describe('elementType isDisallowedReason tests', () => {
    test('FormContainerElementType itself as a nested child.', () => {
      const formContainerElementType = testApp
        .getRegistry()
        .get('element', 'form_container')

      const page = { id: 123 }
      const formAncestor = { id: 111, type: 'form_container', page_id: page.id }
      const columnAncestor1 = {
        id: 112,
        type: 'column',
        page_id: page.id,
        parent_element_id: 111,
      }
      const columnAncestor2 = {
        id: 113,
        type: 'column',
        page_id: page.id,
      }

      page.elementMap = {
        111: formAncestor,
        112: columnAncestor1,
        113: columnAncestor2,
      }

      expect(
        formContainerElementType.isDisallowedReason({
          builder: { id: 1 },
          page,
          parentElement: formAncestor,
          beforeElement: null,
          placeInContainer: 'content',
        })
      ).toEqual('elementType.notAllowedInsideSameType')
      expect(
        formContainerElementType.isDisallowedReason({
          builder: { id: 1 },
          page,
          parentElement: columnAncestor1,
          beforeElement: null,
          placeInContainer: 'content',
        })
      ).toEqual('elementType.notAllowedInsideSameType')
      // We check a top level column element
      expect(
        formContainerElementType.isDisallowedReason({
          builder: { id: 1 },
          page,
          parentElement: columnAncestor2,
          beforeElement: null,
          placeInContainer: 'content',
        })
      ).toEqual(null)
    })
    test('ColumnElementType itself as a nested child.', () => {
      const columnContainerElementType = testApp
        .getRegistry()
        .get('element', 'column')

      const page = { id: 123 }
      const columnAncestor = { id: 111, type: 'column', page_id: page.id }

      page.elementMap = { 111: columnAncestor }

      expect(
        columnContainerElementType.isDisallowedReason({
          builder: { id: 1 },
          page,
          parentElement: columnAncestor,
          beforeElement: null,
          placeInContainer: 'content',
        })
      ).toEqual('elementType.notAllowedInsideSameType')
    })
    test('RepeatElementType allow itself as a nested child.', () => {
      const repeatContainerElementType = testApp
        .getRegistry()
        .get('element', 'repeat')

      const page = { id: 123 }
      const repeatAncestor = { id: 111, type: 'repeat', page_id: page.id }

      page.elementMap = { 111: repeatAncestor }

      expect(
        repeatContainerElementType.isDisallowedReason({
          builder: { id: 1 },
          page,
          parentElement: repeatAncestor,
          beforeElement: null,
          placeInContainer: 'content',
        })
      ).toEqual(null)
    })
  })

  describe('elementTypes ChoiceElementType choiceOptions tests', () => {
    test('choiceOptions returns Value if Value is not null.', () => {
      const elementType = new ChoiceElementType()
      const element = {
        required: true,
        options: [
          { id: 1, value: '', name: 'Foo Name' },
          { id: 2, value: 'bar_name', name: 'Bar Name' },
        ],
      }

      // When the Value is non-null, we expect them to be returned verbatim.
      expect(elementType.choiceOptions(element)).toEqual(['', 'bar_name'])
    })

    test('choiceOptions returns Name if Value is null.', () => {
      const elementType = new ChoiceElementType()
      const element = {
        required: true,
        options: [
          { id: 1, value: null, name: 'Foo Name' },
          { id: 2, value: 'bar_name', name: 'Bar Name' },
        ],
      }

      // When Value is null, we assume the user wants it to be the same as
      // the Name. Thus, we return 'Foo Name' instead of null.
      expect(elementType.choiceOptions(element)).toEqual([
        'Foo Name',
        'bar_name',
      ])
    })

    test('choiceOptions returns Value if it is an empty string.', () => {
      const elementType = new ChoiceElementType()
      const element = {
        required: true,
        options: [
          { id: 1, value: '', name: 'Foo Name' },
          { id: 2, value: 'bar_name', name: 'Bar Name' },
        ],
      }

      // Since an empty string is a valid Value, if the user has explicitly
      // declared it, we should return an empty string.
      expect(elementType.choiceOptions(element)).toEqual(['', 'bar_name'])
    })
  })

  describe('HeadingElementType isInError tests', () => {
    test('Returns true if Heading Element has errors, false otherwise', () => {
      const elementType = testApp.getRegistry().get('element', 'heading')

      // Heading with missing value is invalid
      expect(elementType.isInError({ page: {}, element: { value: '' } })).toBe(
        true
      )

      // Heading with value is valid
      expect(
        elementType.isInError({ page: {}, element: { value: 'Foo Heading' } })
      ).toBe(false)
    })
  })

  describe('TextElementType isInError tests', () => {
    test('Returns true if Text Element has errors, false otherwise', () => {
      const elementType = testApp.getRegistry().get('element', 'text')

      // Text with missing value is invalid
      expect(elementType.isInError({ page: {}, element: { value: '' } })).toBe(
        true
      )

      // Text with value is valid
      expect(
        elementType.isInError({ page: {}, element: { value: 'Foo Text' } })
      ).toBe(false)
    })
  })

  describe('LinkElementType isInError tests', () => {
    test('Returns true if Link Element has errors, false otherwise', () => {
      const elementType = testApp.getRegistry().get('element', 'link')

      // Link with missing text is invalid
      expect(elementType.isInError({ element: { value: '' } })).toBe(true)

      // When navigation_type is 'page' the navigate_to_page_id must be set
      let element = {
        navigation_type: 'page',
        navigate_to_page_id: '',
        value: 'Foo Link',
      }
      expect(elementType.isInError({ page: {}, element })).toBe(true)

      // Otherwise it is valid
      const page = { id: 10, shared: false, order: 1 }
      const builder = { pages: [page] }
      element.navigate_to_page_id = 10
      expect(elementType.isInError({ page, builder, element })).toBe(false)

      // When navigation_type is 'custom' the navigate_to_url must be set
      element = { navigation_type: 'custom', navigate_to_url: '' }
      expect(elementType.isInError({ page, element })).toBe(true)

      // Otherwise it is valid
      element.navigate_to_url = 'http://localhost'
      element.value = 'Foo Link'
      expect(elementType.isInError({ page, element })).toBe(false)
    })
  })

  describe('ImageElementType isInError tests', () => {
    test('Returns true if Image Element has errors, false otherwise', () => {
      const elementType = testApp.getRegistry().get('element', 'image')

      // Image with image_source_type of 'upload' must have an image_file url
      const element = { image_source_type: IMAGE_SOURCE_TYPES.UPLOAD }
      expect(elementType.isInError({ element })).toBe(true)

      // Otherwise it is valid
      element.image_file = { url: 'http://localhost' }
      expect(elementType.isInError({ element })).toBe(false)

      // Image with missing image_url is invalid
      element.image_source_type = ''
      element.image_url = ''
      expect(elementType.isInError({ element })).toBe(true)

      // Otherwise it is valid
      element.image_url = "'http://localhost'"
      expect(elementType.isInError({ element })).toBe(false)
    })
  })

  describe('ButtonElementType isInError tests', () => {
    test('Returns true if Button Element has errors, false otherwise', () => {
      const page = { id: 1, name: 'Foo Page', workflowActions: [] }
      const element = { id: 50, value: '', page_id: page.id }
      const elementType = testApp.getRegistry().get('element', 'button')

      // Button with missing value is invalid
      expect(elementType.isInError({ page, element })).toBe(true)

      // Button with value but missing workflowActions is invalid
      element.value = 'click me'
      expect(elementType.isInError({ page, element })).toBe(true)

      // Button with value and workflowAction is valid
      page.workflowActions = [{ element_id: 50 }]
      expect(elementType.isInError({ page, element })).toBe(false)
    })
  })

  describe('IFrameElementType isInError tests', () => {
    test('Returns true if IFrame Element has errors, false otherwise', () => {
      const elementType = testApp.getRegistry().get('element', 'iframe')

      // IFrame with source_type of 'url' and missing url is invalid
      const element = { source_type: IFRAME_SOURCE_TYPES.URL }
      expect(elementType.isInError({ element })).toBe(true)

      // Otherwise it is valid
      element.url = 'http://localhost'
      expect(elementType.isInError({ element })).toBe(false)

      // IFrame with source_type of 'embed' and missing embed is invalid
      element.source_type = IFRAME_SOURCE_TYPES.EMBED
      expect(elementType.isInError({ element })).toBe(true)

      // Otherwise it is valid
      element.embed = 'http://localhost'
      expect(elementType.isInError({ element })).toBe(false)

      // Default is to return no errors
      element.source_type = 'foo'
      expect(elementType.isInError({ element })).toBe(false)
    })
  })

  describe('FormContainerElementType isInError tests', () => {
    test('Returns true if Form Container Element has errors, false otherwise', () => {
      const page = { id: 1, name: 'Foo Page', workflowActions: [] }
      const element = {
        id: 50,
        submit_button_label: 'Submit',
        page_id: page.id,
      }
      page.elementMap = { 50: element }
      page.orderedElements = [element]

      const elementType = testApp.getRegistry().get('element', 'form_container')

      // Invalid if we have no workflow actions
      expect(elementType.isInError({ page, element })).toBe(true)

      // Invalid if we have no children
      page.workflowActions = [{ element_id: 50 }]
      expect(elementType.isInError({ page, element })).toBe(true)

      // Valid as we have all required fields
      const childElement = {
        id: 51,
        type: 'input_text',
        page_id: page.id,
        parent_element_id: element.id,
      }
      page.elementMap = { 50: element, 51: childElement }
      page.orderedElements = [element, childElement]
      expect(elementType.isInError({ page, element })).toBe(false)
    })
  })

  describe.only('elementType elementAround tests', () => {
    let page, sharedPage, builder
    beforeEach(async () => {
      // Populate a page with a bunch of elements
      page = { id: 123, elements: [], orderedElements: [], elementMap: {} }
      sharedPage = {
        id: 124,
        shared: true,
        elements: [],
        orderedElements: [],
        elementMap: {},
      }
      builder = { id: 1, pages: [sharedPage, page] }

      const heading1 = {
        id: 42,
        type: 'heading',
      }
      const heading2 = {
        id: 43,
        type: 'heading',
      }
      const elements = [heading1, heading2]

      await Promise.all(
        elements.map(async (element, index) => {
          await testApp.getStore().dispatch('element/forceCreate', {
            page,
            element: {
              place_in_container: null,
              parent_element_id: null,
              ...element,
              page_id: page.id,
              order: `${index}.0000`,
            },
          })
        })
      )

      const header1 = {
        id: 111,
        type: 'header',
      }
      const header2 = {
        id: 112,
        type: 'header',
      }
      const footer1 = {
        id: 113,
        type: 'footer',
      }
      const footer2 = {
        id: 114,
        type: 'footer',
      }

      const sharedPageElements = [header1, footer1, footer2, header2]

      await Promise.all(
        sharedPageElements.map(async (element, index) => {
          await testApp.getStore().dispatch('element/forceCreate', {
            page: sharedPage,
            element: {
              place_in_container: null,
              parent_element_id: null,
              ...element,
              page_id: sharedPage.id,
              order: `${index}.0000`,
            },
          })
        })
      )
    })
    test('for first header.', () => {
      const elementType = testApp.getRegistry().get('element', 'header')
      const firstHeader = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 111)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: firstHeader,
        withSharedPage: false,
      })
      expect(elementsAround.before).toBeNull()
      expect(elementsAround.after?.id).toEqual(112)
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for second header.', () => {
      const elementType = testApp.getRegistry().get('element', 'header')
      const secondHeader = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 112)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: secondHeader,
        withSharedPage: false,
      })
      expect(elementsAround.before?.id).toEqual(111)
      expect(elementsAround.after).toBeNull()
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for second header with sharedPage.', () => {
      const elementType = testApp.getRegistry().get('element', 'header')
      const secondHeader = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 112)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: secondHeader,
        withSharedPage: true,
      })
      expect(elementsAround.before?.id).toEqual(111)
      expect(elementsAround.after?.id).toEqual(42)
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for first footer.', () => {
      const elementType = testApp.getRegistry().get('element', 'footer')
      const firstFooter = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 113)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: firstFooter,
        withSharedPage: false,
      })
      expect(elementsAround.before).toBeNull()
      expect(elementsAround.after?.id).toEqual(114)
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for first footer with shared page.', () => {
      const elementType = testApp.getRegistry().get('element', 'footer')
      const firstFooter = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 113)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: firstFooter,
        withSharedPage: true,
      })
      expect(elementsAround.before?.id).toEqual(43)
      expect(elementsAround.after?.id).toEqual(114)
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for second footer.', () => {
      const elementType = testApp.getRegistry().get('element', 'footer')
      const secondFooter = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 114)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: secondFooter,
        withSharedPage: false,
      })
      expect(elementsAround.before?.id).toEqual(113)
      expect(elementsAround.after).toBeNull()
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for first heading.', () => {
      const elementType = testApp.getRegistry().get('element', 'heading')
      const firstHeading = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 42)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: firstHeading,
        withSharedPage: false,
      })
      expect(elementsAround.before).toBeNull()
      expect(elementsAround.after?.id).toEqual(43)
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for second heading.', () => {
      const elementType = testApp.getRegistry().get('element', 'heading')
      const secondHeading = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 43)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: secondHeading,
        withSharedPage: false,
      })
      expect(elementsAround.before?.id).toEqual(42)
      expect(elementsAround.after).toBeNull()
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for first heading with shared page.', () => {
      const elementType = testApp.getRegistry().get('element', 'heading')
      const firstHeading = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 42)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: firstHeading,
        withSharedPage: true,
      })
      expect(elementsAround.before?.id).toEqual(112)
      expect(elementsAround.after?.id).toEqual(43)
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
    test('for second heading  with shared page.', () => {
      const elementType = testApp.getRegistry().get('element', 'heading')
      const secondHeading = testApp
        .getStore()
        .getters['element/getElementByIdInPages']([page, sharedPage], 43)
      const elementsAround = elementType.getElementsAround({
        builder,
        page,
        element: secondHeading,
        withSharedPage: true,
      })
      expect(elementsAround.before?.id).toEqual(42)
      expect(elementsAround.after?.id).toEqual(113)
      expect(elementsAround.left).toBeNull()
      expect(elementsAround.right).toBeNull()
    })
  })
})
