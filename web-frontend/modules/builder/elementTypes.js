import { Registerable } from '@baserow/modules/core/registry'
import TextElement from '@baserow/modules/builder/components/elements/components/TextElement'
import HeadingElement from '@baserow/modules/builder/components/elements/components/HeadingElement'
import LinkElement from '@baserow/modules/builder/components/elements/components/LinkElement'
import TextElementForm from '@baserow/modules/builder/components/elements/components/forms/general/TextElementForm'
import HeadingElementForm from '@baserow/modules/builder/components/elements/components/forms/general/HeadingElementForm'
import LinkElementForm from '@baserow/modules/builder/components/elements/components/forms/general/LinkElementForm'
import ImageElementForm from '@baserow/modules/builder/components/elements/components/forms/general/ImageElementForm'
import ImageElement from '@baserow/modules/builder/components/elements/components/ImageElement'
import InputTextElement from '@baserow/modules/builder/components/elements/components/InputTextElement'
import InputTextElementForm from '@baserow/modules/builder/components/elements/components/forms/general/InputTextElementForm'
import TableElement from '@baserow/modules/builder/components/elements/components/TableElement'
import TableElementForm from '@baserow/modules/builder/components/elements/components/forms/general/TableElementForm'
import {
  ensureArray,
  ensureBoolean,
  ensureInteger,
  ensureString,
  ensureStringOrInteger,
} from '@baserow/modules/core/utils/validator'
import {
  CHOICE_OPTION_TYPES,
  DATE_FORMATS,
  TIME_FORMATS,
  IMAGE_SOURCE_TYPES,
  IFRAME_SOURCE_TYPES,
  DIRECTIONS,
  PAGE_PLACES,
} from '@baserow/modules/builder/enums'
import ColumnElement from '@baserow/modules/builder/components/elements/components/ColumnElement'
import ColumnElementForm from '@baserow/modules/builder/components/elements/components/forms/general/ColumnElementForm'
import DefaultStyleForm from '@baserow/modules/builder/components/elements/components/forms/style/DefaultStyleForm'
import ButtonElement from '@baserow/modules/builder/components/elements/components/ButtonElement'
import ButtonElementForm from '@baserow/modules/builder/components/elements/components/forms/general/ButtonElementForm'
import { ClickEvent, SubmitEvent } from '@baserow/modules/builder/eventTypes'
import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import { resolveFormula } from '@baserow/modules/core/formula'
import FormContainerElement from '@baserow/modules/builder/components/elements/components/FormContainerElement.vue'
import FormContainerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/FormContainerElementForm.vue'
import ChoiceElement from '@baserow/modules/builder/components/elements/components/ChoiceElement.vue'
import ChoiceElementForm from '@baserow/modules/builder/components/elements/components/forms/general/ChoiceElementForm.vue'
import CheckboxElement from '@baserow/modules/builder/components/elements/components/CheckboxElement.vue'
import CheckboxElementForm from '@baserow/modules/builder/components/elements/components/forms/general/CheckboxElementForm.vue'
import IFrameElement from '@baserow/modules/builder/components/elements/components/IFrameElement.vue'
import IFrameElementForm from '@baserow/modules/builder/components/elements/components/forms/general/IFrameElementForm.vue'
import RepeatElement from '@baserow/modules/builder/components/elements/components/RepeatElement'
import RepeatElementForm from '@baserow/modules/builder/components/elements/components/forms/general/RepeatElementForm'
import RecordSelectorElement from '@baserow/modules/builder/components/elements/components/RecordSelectorElement.vue'
import RecordSelectorElementForm from '@baserow/modules/builder/components/elements/components/forms/general/RecordSelectorElementForm'
import MultiPageContainerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/MultiPageContainerElementForm'
import MultiPageContainerElement from '@baserow/modules/builder/components/elements/components/MultiPageContainerElement'
import DateTimePickerElement from '@baserow/modules/builder/components/elements/components/DateTimePickerElement'
import DateTimePickerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/DateTimePickerElementForm'
import { pathParametersInError } from '@baserow/modules/builder/utils/params'
import {
  ContainerElementTypeMixin,
  CollectionElementTypeMixin,
  MultiPageElementTypeMixin,
} from '@baserow/modules/builder/elementTypeMixins'
import { isNumeric, isValidEmail } from '@baserow/modules/core/utils/string'
import { FormattedDate, FormattedDateTime } from '@baserow/modules/builder/date'

export class ElementType extends Registerable {
  get name() {
    return null
  }

  get description() {
    return null
  }

  get iconClass() {
    return null
  }

  get component() {
    return null
  }

  get editComponent() {
    return this.component
  }

  get generalFormComponent() {
    return null
  }

  get styleFormComponent() {
    return DefaultStyleForm
  }

  get stylesAll() {
    return [
      'style_padding_top',
      'style_padding_bottom',
      'style_padding_left',
      'style_padding_right',
      'style_margin_top',
      'style_margin_bottom',
      'style_margin_left',
      'style_margin_right',
      'style_border_top',
      'style_border_bottom',
      'style_border_left',
      'style_border_right',
      'style_background',
      'style_background_color',
      'style_background_file',
      'style_background_mode',
      'style_width',
    ]
  }

  /**
   * Returns the current place of the given element.
   *
   * @param {Object} element
   * @returns a PAGE_PLACES enum
   */
  getPagePlace() {
    return PAGE_PLACES.CONTENT
  }

  /**
   * Returns the reason why this element type is disallowed for the given location.
   * @param {Object} builder the current builder object
   * @param {Object} page the current page
   * @param {Object} parentElement the parent container element in which we want to
   *   add the element in if any.
   * @param {Object} beforeElement the element before which we want to add the element.
   * @param {Object} placeInContainer The place in the container if we are in a
   *   container
   * @param {Object} pagePlace the page place we want to add the element to.
   * @returns null if the element type is allowed or a string explaining the reason why
   *   the element type is not allowed at the given location.
   */
  isDisallowedReason({
    builder,
    page: destinationPage,
    parentElement,
    beforeElement,
    placeInContainer,
    pagePlace,
  }) {
    if (!parentElement) {
      const sharedPage = this.app.store.getters['page/getSharedPage'](builder)

      if (pagePlace === PAGE_PLACES.HEADER) {
        if (beforeElement && beforeElement.page_id === sharedPage.id) {
          // It's not allowed to add these elements as root inside header before
          // another multi page element
          return this.app.i18n.t('elementType.notAllowedLocation')
        }
      }

      if (pagePlace === PAGE_PLACES.FOOTER) {
        if (!beforeElement) {
          // Not allowed as last child of footer
          return this.app.i18n.t('elementType.notAllowedLocation')
        } else {
          const footerElements = this.app.store.getters[
            'element/getRootElements'
          ](sharedPage).filter(
            (element) =>
              this.app.$registry.get('element', element.type).getPagePlace() ===
              PAGE_PLACES.FOOTER
          )
          if (beforeElement.id !== footerElements[0].id) {
            // It's not allowed to add these elements as root inside footer after
            // another multi page element
            return this.app.i18n.t('elementType.notAllowedLocation')
          }
        }
      }
    }
    return null
  }

  get styles() {
    return this.stylesAll
  }

  /**
   * Returns a display name for this element, so it can be distinguished from
   * other elements of the same type.
   * @param {object} element - The element we want to get a display name for.
   * @param {object} applicationContext - The context of the current application
   * @returns {string} this element's display name.
   */
  getDisplayName(element, applicationContext) {
    return this.name
  }

  getEvents(element) {
    return []
  }

  getEventByName(element, name) {
    return this.getEvents(element).find((event) => event.name === name)
  }

  /**
   * Should return whether this element is visible.
   * @param {Object} element the element to check
   * @param {Object} currentPage the current displayed page
   * @returns
   */
  isVisible({ element, currentPage }) {
    return true
  }

  /**
   * Returns whether the element configuration is valid or not.
   * @param {object} param An object containing the page, element, and builder
   * @returns true if the element is in error
   */
  isInError({ page, element, builder }) {
    return false
  }

  /**
   * Allow to hook into default values for this element type at element creation.
   * @param {object} values the current values for the element to create.
   * @returns an object containing values updated with the default values.
   */
  getDefaultValues(page, values) {
    // By default if an element is inside a container we apply the
    // `.getDefaultChildValues()` method of the parent to it.
    if (values?.parent_element_id) {
      const parentElement = this.app.store.getters['element/getElementById'](
        page,
        values.parent_element_id
      )
      const parentElementType = this.app.$registry.get(
        'element',
        parentElement.type
      )
      return {
        ...values,
        ...parentElementType.getDefaultChildValues(page, values),
      }
    }
    return values
  }

  /**
   * When a data source is modified or destroyed, `element/emitElementEvent`
   * can be dispatched to notify all elements of the event. Element types
   * can implement this function to handle the cases.
   *
   * @param event - `ELEMENT_EVENTS.DATA_SOURCE_REMOVED` if a data source
   *  has been destroyed, or `ELEMENT_EVENTS.DATA_SOURCE_AFTER_UPDATE` if
   *  it's been updated.
   * @param params - Context data which the element type can use.
   */
  onElementEvent(event, params) {}

  resolveFormula(formula, applicationContext) {
    const formulaFunctions = {
      get: (name) => {
        return this.app.$registry.get('runtimeFormulaFunction', name)
      },
    }

    const runtimeFormulaContext = new Proxy(
      new RuntimeFormulaContext(
        this.app.$registry.getAll('builderDataProvider'),
        applicationContext
      ),
      {
        get(target, prop) {
          return target.get(prop)
        },
      }
    )

    return resolveFormula(formula, formulaFunctions, runtimeFormulaContext)
  }

  /**
   * Responsible for returning an array of collection element IDs that represent
   * the ancestry of this element. It's used to determine the accessible path
   * between elements that have access to the form data provider. If an element
   * is in the path of a form element, then it can use its form data.
   *
   * @param {Object} element - The element we're the path for.
   * @param {Object} page - The page the element belongs to.
   */
  getElementNamespacePath(element, page) {
    const ancestors = this.app.store.getters['element/getAncestors'](
      page,
      element
    )
    return ancestors
      .map((ancestor) => {
        const elementType = this.app.$registry.get('element', ancestor.type)
        return elementType.isCollectionElement ? ancestor.id : null
      })
      .filter((id) => id !== null)
      .reverse()
  }

  /**
   * A hook that is triggered right after an element is created.
   *
   * @param element - The element that was just created
   * @param page - The page the element belongs to
   */
  afterCreate(element, page) {}

  /**
   * A hook that is triggered right after an element is deleted.
   *
   * @param element - The element that was just deleted
   * @param page - The page the element belongs to
   */
  afterDelete(element, page) {}

  /**
   * A hook that is trigger right after an element has been updated.
   * @param element - The updated element
   * @param page - The page the element belong to
   */
  afterUpdate(element, page) {}

  /**
   * Returns the places for this element. The places are the location where we can place
   * a child element. Only collection elements can have places.
   *
   * @param {Object} element
   * @returns an array of allowed places for the given collection element.
   */
  getElementPlaces(element) {
    return []
  }

  /**
   * Returns the places if we move an element in the four directions. Used when we want
   * to now if we can move an element in a certain direction and what place it will be.
   *
   * @param {Object} page the page we want the places for. Usually the current page.
   * @param {Object} element the element we want the next places for.
   * @returns an object keyed by the four direction and for each `null` or an object
   *  containing:
   * {
   *   beforeElementId,
   *   parentElementId,
   *   placeInContainer,
   * }
   * that can be used to move the element.
   */
  getNextPlaces({ builder, page, element }) {
    let placeInContainer = element.place_in_container
    const parentElementId = element.parent_element_id
      ? element.parent_element_id
      : null

    const elementPage = this.app.store.getters['page/getById'](
      builder,
      element.page_id
    )

    const parentElement = element.parent_element_id
      ? this.app.store.getters['element/getElementById'](
          elementPage,
          element.parent_element_id
        )
      : null
    const parentElementType = parentElement
      ? this.app.$registry.get('element', parentElement.type)
      : null

    const elementsAround = this.getElementsAround({ builder, page, element })

    const nextPlaces = {
      [DIRECTIONS.BEFORE]: null,
      [DIRECTIONS.AFTER]: null,
      [DIRECTIONS.LEFT]: null,
      [DIRECTIONS.RIGHT]: null,
    }

    // BEFORE
    const previousElement = elementsAround[DIRECTIONS.BEFORE]
    if (previousElement) {
      // If we have a previous element, let place it before it.
      nextPlaces[DIRECTIONS.BEFORE] = {
        beforeElementId: previousElement.id,
        parentElementId,
        placeInContainer: previousElement.place_in_container,
      }
    }

    // AFTER
    const nextElement = elementsAround[DIRECTIONS.AFTER]
    if (nextElement) {
      const nextNextElement = this.app.store.getters['element/getNextElement'](
        elementPage,
        nextElement
      )
      if (!nextNextElement) {
        // We have to place this element as last element in the given place
        nextPlaces[DIRECTIONS.AFTER] = {
          beforeElementId: null,
          parentElementId,
          placeInContainer: element.place_in_container,
        }
      } else {
        // Otherwise it must be placed just before the next next element
        nextPlaces[DIRECTIONS.AFTER] = {
          beforeElementId: nextNextElement.id,
          parentElementId,
          placeInContainer: nextNextElement.place_in_container,
        }
      }
    }

    // LEFT
    if (parentElement) {
      const places = parentElementType.getElementPlaces(parentElement)
      const placeIndex = places.findIndex(
        (place) => place === element.place_in_container
      )

      if (placeIndex > 0) {
        // Let's move it as last of the previous container place
        nextPlaces[DIRECTIONS.LEFT] = {
          beforeElementId: null,
          parentElementId,
          placeInContainer: places[placeIndex - 1],
        }
      }
    }

    // RIGHT
    if (parentElement) {
      const places = parentElementType.getElementPlaces(parentElement)
      const placeIndex = places.findIndex(
        (place) => place === element.place_in_container
      )
      if (placeIndex < places.length - 1) {
        placeInContainer = places[placeIndex + 1]
        const elementsInNextPlace = this.app.store.getters[
          'element/getElementsInPlace'
        ](elementPage, element.parent_element_id, placeInContainer)
        if (elementsInNextPlace.length) {
          // Let's place it as first element in the next container place
          nextPlaces[DIRECTIONS.RIGHT] = {
            beforeElementId: elementsInNextPlace[0].id,
            parentElementId,
            placeInContainer,
          }
        } else {
          nextPlaces[DIRECTIONS.RIGHT] = {
            beforeElementId: null,
            parentElementId,
            placeInContainer,
          }
        }
      }
    }
    return nextPlaces
  }

  /**
   * Returns the elements around the current element in the four directions if the
   * element exists. The simplified base logic is the following:
   * - If the element is at root level:
   *   - The BEFORE element is the previous sibling in the element order
   *   - The AFTER element is the next sibling in the element order
   *   - No LEFT nor RIGHT elements.
   * - If the element is inside container
   *   - BEFORE and AFTER are the previous and next in order
   *   - LEFT if the last element of the container previous place if it exists
   *   - RIGHT is the first element of the container next place if it exists
   * if `withSharedPage` is true, we consider the header and footer elements as if
   * they were on the same page respectively before and after the current page elements.
   * @param {Object} page the current page
   * @param {Object} element the element we want the elements around
   * @param {Boolean} withSharedPage whether we want to consider the shared page or not.
   * @returns an object keyed by the directions and valued by the elements
   * or null if there is no element in that direction.
   */
  getElementsAround({ builder, page, element, withSharedPage = false }) {
    const elementType = this.app.$registry.get('element', element.type)
    const elementPlace = elementType.getPagePlace()
    const isRootElement = !element.parent_element_id

    const elementPage = this.app.store.getters['page/getById'](
      builder,
      element.page_id
    )

    const siblings = this.app.store.getters['element/getElementsInPlace'](
      elementPage,
      element.parent_element_id,
      element.place_in_container
    ).filter(
      (sibling) =>
        Boolean(element.parent_element_id) ||
        this.app.$registry.get('element', sibling.type).getPagePlace() ===
          elementPlace
    )

    const elementIndex = siblings.findIndex((e) => e.id === element.id)

    let previousElement = null
    let nextElement = null

    if (elementIndex > 0) {
      previousElement = siblings[elementIndex - 1]
    }

    if (elementIndex < siblings.length - 1) {
      nextElement = siblings[elementIndex + 1]
    }

    // If we are considering the shared page and we have no previous or next element
    // we want to potentially use the elements from the shared page
    if (withSharedPage && isRootElement) {
      const sharedPage = this.app.store.getters['page/getSharedPage'](builder)

      if (!previousElement) {
        // no previous element and we are in the page content, then previous element
        // could come from the HEADER
        if (elementPlace === PAGE_PLACES.CONTENT) {
          const headerElements = this.app.store.getters[
            'element/getRootElements'
          ](sharedPage).filter(
            (element) =>
              this.app.$registry.get('element', element.type).getPagePlace() ===
              PAGE_PLACES.HEADER
          )
          if (headerElements.length) {
            previousElement = headerElements.at(-1)
          }
        } else if (elementPlace === PAGE_PLACES.FOOTER) {
          // previous element could come from the page CONTENT if we don't have previous
          // yet
          const contentElements =
            this.app.store.getters['element/getRootElements'](page)
          if (contentElements.length) {
            previousElement = contentElements.at(-1)
          }
        }
      }

      // Let's consider the shared page element as next element.
      // If the current element is in the HEADER, it might be a CONTENT element
      // If it's a CONTENT element it could be in the FOOTER.
      if (!nextElement) {
        if (elementPlace === PAGE_PLACES.HEADER) {
          const contentElements =
            this.app.store.getters['element/getRootElements'](page)
          if (contentElements.length) {
            nextElement = contentElements[0]
          }
        } else if (elementPlace === PAGE_PLACES.CONTENT) {
          const footerElements = this.app.store.getters[
            'element/getRootElements'
          ](sharedPage).filter(
            (element) =>
              this.app.$registry.get('element', element.type).getPagePlace() ===
              PAGE_PLACES.FOOTER
          )
          if (footerElements.length) {
            nextElement = footerElements[0]
          }
        }
      }
    }

    let leftElement = null
    let rightElement = null

    // We have a parent, so we can find left and right elements.
    if (element.parent_element_id) {
      const parentElement = this.app.store.getters['element/getElementById'](
        elementPage,
        element.parent_element_id
      )
      const parentElementType = this.app.$registry.get(
        'element',
        parentElement.type
      )
      const places = parentElementType.getElementPlaces(parentElement)
      const placeIndex = places.findIndex(
        (place) => place === element.place_in_container
      )

      let placeLeftIndex = placeIndex - 1
      while (placeLeftIndex >= 0) {
        const elementsInNextPlace = this.app.store.getters[
          'element/getElementsInPlace'
        ](elementPage, element.parent_element_id, places[placeLeftIndex])
        if (elementsInNextPlace.length > 0) {
          leftElement = elementsInNextPlace.at(-1)
          break
        }
        placeLeftIndex -= 1
      }
      let placeRightIndex = placeIndex + 1
      while (placeRightIndex <= places.length - 1) {
        const elementsInNextPlace = this.app.store.getters[
          'element/getElementsInPlace'
        ](elementPage, element.parent_element_id, places[placeRightIndex])
        if (elementsInNextPlace.length > 0) {
          rightElement = elementsInNextPlace[0]
          break
        }
        placeRightIndex += 1
      }
    }

    return {
      [DIRECTIONS.BEFORE]: previousElement,
      [DIRECTIONS.AFTER]: nextElement,
      [DIRECTIONS.LEFT]: leftElement,
      [DIRECTIONS.RIGHT]: rightElement,
    }
  }

  /**
   * Generates a unique element id based on the element and if provided, an array
   * representing a path to access form data. Most elements will have a unique
   * ID that matches their `id`, but when an element is part of one or more repeats,
   * we need to ensure that the ID is unique for each record.
   *
   * @param {Object} element - The element we want to generate a unique ID for.
   * @param {Array} recordIndexPath - An array of integers which represent the
   * record indices we've accumulated through nested collection element ancestors.
   * @returns {String} - The unique element ID.
   *
   */
  uniqueElementId(element, recordIndexPath) {
    return [element.id, ...(recordIndexPath || [])].join('.')
  }

  /**
   * Responsible for optionally extending the element store's
   * `_` object with per-element type specific properties.
   * @returns {Object} - An object containing the properties to be added.
   */
  getPopulateStoreProperties() {
    return {}
  }

  /**
   * Given a `page` and an `element`, and `ancestorType`, returns whether the
   * element has an ancestor of a specified element type.
   *
   * @param {Object} page - The page the element belongs to.
   * @param {Object} element - The element to check for ancestors.
   * @param {String} ancestorType - The ancestor type to check for.
   * @returns {Boolean} Whether the element has an ancestor of the specified type.
   */
  hasAncestorOfType(page, element, ancestorType) {
    return this.app.store.getters['element/getAncestors'](page, element).some(
      ({ type }) => type === ancestorType
    )
  }
}

export class FormContainerElementType extends ContainerElementTypeMixin(
  ElementType
) {
  static getType() {
    return 'form_container'
  }

  get name() {
    return this.app.i18n.t('elementType.formContainer')
  }

  get description() {
    return this.app.i18n.t('elementType.formContainerDescription')
  }

  get iconClass() {
    return 'iconoir-frame'
  }

  get component() {
    return FormContainerElement
  }

  get generalFormComponent() {
    return FormContainerElementForm
  }

  getElementPlaces(element) {
    return [null]
  }

  /**
   * This element is not allowed in another form container.
   */
  isDisallowedReason({
    builder,
    page,
    parentElement,
    beforeElement,
    placeInContainer,
    pagePlace,
  }) {
    if (parentElement) {
      const hasSameTypeAncestor = !!this.app.store.getters[
        'element/getAncestors'
      ](page, parentElement, {
        predicate: (ancestor) => ancestor.type === this.type,
        includeSelf: true,
      }).length
      if (hasSameTypeAncestor) {
        return this.app.i18n.t('elementType.notAllowedInsideSameType')
      }
    }
    return super.isDisallowedReason({
      builder,
      page,
      parentElement,
      beforeElement,
      placeInContainer,
      pagePlace,
    })
  }

  get childStylesForbidden() {
    return ['style_width']
  }

  getEvents(element) {
    return [new SubmitEvent({ ...this.app })]
  }

  /**
   * A form container is invalid if it has no workflow actions, or it has no
   * children.
   */
  isInError({ page, element }) {
    const workflowActions = this.app.store.getters[
      'workflowAction/getElementWorkflowActions'
    ](page, element.id)

    if (!workflowActions.length) {
      return true
    }

    return super.isInError({ page, element })
  }
}

export class ColumnElementType extends ContainerElementTypeMixin(ElementType) {
  static getType() {
    return 'column'
  }

  get name() {
    return this.app.i18n.t('elementType.column')
  }

  get description() {
    return this.app.i18n.t('elementType.columnDescription')
  }

  get iconClass() {
    return 'iconoir-view-columns-3'
  }

  get component() {
    return ColumnElement
  }

  get generalFormComponent() {
    return ColumnElementForm
  }

  getElementPlaces(element) {
    return [...Array(element.column_amount)].map((_, index) => `${index}`)
  }

  /**
   * This element is not allowed in another column container.
   */
  isDisallowedReason({
    builder,
    page,
    parentElement,
    beforeElement,
    placeInContainer,
    pagePlace,
  }) {
    if (parentElement) {
      const hasSameTypeAncestor = !!this.app.store.getters[
        'element/getAncestors'
      ](page, parentElement, {
        predicate: (ancestor) => ancestor.type === this.type,
        includeSelf: true,
      }).length
      if (hasSameTypeAncestor) {
        return this.app.i18n.t('elementType.notAllowedInsideSameType')
      }
    }
    return super.isDisallowedReason({
      builder,
      page,
      parentElement,
      beforeElement,
      placeInContainer,
      pagePlace,
    })
  }

  get childStylesForbidden() {
    return ['style_width']
  }

  get defaultPlaceInContainer() {
    return '0'
  }
}

export class TableElementType extends CollectionElementTypeMixin(ElementType) {
  static getType() {
    return 'table'
  }

  get name() {
    return this.app.i18n.t('elementType.table')
  }

  get description() {
    return this.app.i18n.t('elementType.tableDescription')
  }

  get iconClass() {
    return 'iconoir-table'
  }

  get component() {
    return TableElement
  }

  get generalFormComponent() {
    return TableElementForm
  }

  getEvents(element) {
    return (element.fields || [])
      .map((field) => {
        const { type, name, uid } = field
        const collectionFieldType = this.app.$registry.get(
          'collectionField',
          type
        )
        return collectionFieldType.events.map((EventType) => {
          return new EventType({
            ...this.app,
            namePrefix: uid,
            labelSuffix: `- ${name}`,
            applicationContextAdditions: { allowSameElement: true },
          })
        })
      })
      .flat()
  }

  /**
   * The table is in error if the configuration is invalid (see collection element
   * mixin) or if one of the fields are in error.
   */
  isInError({ page, element, builder }) {
    return (
      super.isInError({ page, element, builder }) ||
      element.fields.some((collectionField) => {
        const collectionFieldType = this.app.$registry.get(
          'collectionField',
          collectionField.type
        )
        return collectionFieldType.isInError({
          field: collectionField,
          builder,
        })
      })
    )
  }
}

export class RepeatElementType extends CollectionElementTypeMixin(
  ContainerElementTypeMixin(ElementType)
) {
  static getType() {
    return 'repeat'
  }

  get name() {
    return this.app.i18n.t('elementType.repeat')
  }

  get description() {
    return this.app.i18n.t('elementType.repeatDescription')
  }

  get iconClass() {
    return 'iconoir-repeat'
  }

  get component() {
    return RepeatElement
  }

  get generalFormComponent() {
    return RepeatElementForm
  }

  getElementPlaces(element) {
    return [null]
  }

  /**
   * Responsible for extending the element store's `populateElement`
   * `_` object with repeat element specific properties.
   * @returns {Object} - An object containing the properties to be added.
   */
  getPopulateStoreProperties() {
    return { collapsed: false }
  }
}

/**
 * This class serves as a parent class for all form element types. Form element types
 * are all elements that can be used as part of a form. So in simple terms, any element
 * that can represents data in a way that is directly modifiable by an application user.
 */
export class FormElementType extends ElementType {
  isFormElement = true

  formDataType(element) {
    return null
  }

  /**
   * Given a form element, and a form data value, is responsible for validating
   * this form element type against that value. Returns whether the value is valid.
   * @param element - The form element
   * @param value - The value to be validated against
   * @param applicationContext - The context of the current application
   * @returns {boolean}
   */
  isValid(element, value) {
    return !(element.required && !value)
  }

  /**
   * Get the initial form data value of an element.
   * @param element - The form element
   * @param applicationContext - The context of the current application
   * @returns {any} - The initial data that's supposed to be stored
   */
  getInitialFormDataValue(element, applicationContext) {
    throw new Error('.getInitialFormDataValue needs to be implemented')
  }

  /**
   * Returns a display name for this element, so it can be distinguished from
   * other elements of the same type.
   * @param {object} element - The element we want to get a display name for.
   * @param {object} applicationContext
   * @returns {string} this element's display name.
   */
  getDisplayName(element, applicationContext) {
    if (element.label) {
      const resolvedName = ensureString(
        this.resolveFormula(element.label, applicationContext)
      ).trim()
      return resolvedName || this.name
    }
    return this.name
  }

  afterDelete(element, page) {
    return this.app.store.dispatch('formData/removeFormData', {
      page,
      elementId: element.id,
    })
  }

  getDataSchema(element) {
    return {
      type: this.formDataType(element),
    }
  }
}

export class InputTextElementType extends FormElementType {
  static getType() {
    return 'input_text'
  }

  isValid(element, value, applicationContext) {
    if (!value) {
      return !element.required
    }

    switch (element.validation_type) {
      case 'integer':
        return isNumeric(value)
      case 'email':
        return isValidEmail(value)
      default:
        return true
    }
  }

  get name() {
    return this.app.i18n.t('elementType.inputText')
  }

  get description() {
    return this.app.i18n.t('elementType.inputTextDescription')
  }

  get iconClass() {
    return 'iconoir-input-field'
  }

  get component() {
    return InputTextElement
  }

  get generalFormComponent() {
    return InputTextElementForm
  }

  formDataType(element) {
    return 'string'
  }

  getDisplayName(element, applicationContext) {
    const displayValue =
      element.label || element.default_value || element.placeholder

    if (displayValue?.trim()) {
      const resolvedName = ensureString(
        this.resolveFormula(displayValue, applicationContext)
      ).trim()
      return resolvedName || this.name
    }
    return this.name
  }

  getInitialFormDataValue(element, applicationContext) {
    try {
      return this.resolveFormula(element.default_value, {
        element,
        ...applicationContext,
      })
    } catch {
      return ''
    }
  }
}

export class HeadingElementType extends ElementType {
  static getType() {
    return 'heading'
  }

  get name() {
    return this.app.i18n.t('elementType.heading')
  }

  get description() {
    return this.app.i18n.t('elementType.headingDescription')
  }

  get iconClass() {
    return 'iconoir-text'
  }

  get component() {
    return HeadingElement
  }

  get generalFormComponent() {
    return HeadingElementForm
  }

  /**
   * A value is mandatory for the Heading element. Return true if the value
   * is empty to indicate an error, otherwise return false.
   */
  isInError({ element }) {
    return element.value.length === 0
  }

  getDisplayName(element, applicationContext) {
    if (element.value && element.value.length) {
      const resolvedName = ensureString(
        this.resolveFormula(element.value, applicationContext)
      ).trim()
      return resolvedName || this.name
    }
    return this.name
  }
}

export class TextElementType extends ElementType {
  static getType() {
    return 'text'
  }

  get name() {
    return this.app.i18n.t('elementType.text')
  }

  get description() {
    return this.app.i18n.t('elementType.textDescription')
  }

  get iconClass() {
    return 'iconoir-text-box'
  }

  get component() {
    return TextElement
  }

  get generalFormComponent() {
    return TextElementForm
  }

  /**
   * A value is mandatory for the Text element. Return true if the value
   * is empty to indicate an error, otherwise return false.
   */
  isInError({ element }) {
    return element.value.length === 0
  }

  getDisplayName(element, applicationContext) {
    if (element.value) {
      const resolvedName = ensureString(
        this.resolveFormula(element.value, applicationContext)
      ).trim()
      return resolvedName || this.name
    }
    return this.name
  }
}

export class LinkElementType extends ElementType {
  static getType() {
    return 'link'
  }

  get name() {
    return this.app.i18n.t('elementType.link')
  }

  get description() {
    return this.app.i18n.t('elementType.linkDescription')
  }

  get iconClass() {
    return 'iconoir-link'
  }

  get component() {
    return LinkElement
  }

  get generalFormComponent() {
    return LinkElementForm
  }

  /**
   * LinkElement validation returns true if the element is misconfigured,
   * otherwise return false.
   *
   * When the Navigate To is a Page, the page and the path parameters must
   * be valid.
   *
   * When the Navigate To is a Custom URL, a Destination URL value must be
   * provided.
   */
  isInError({ element, builder }) {
    // A Link without any text isn't usable
    if (!element.value) {
      return true
    }

    if (element.navigation_type === 'page') {
      if (!element.navigate_to_page_id) {
        return true
      }
      return pathParametersInError(
        element,
        this.app.store.getters['page/getVisiblePages'](builder)
      )
    } else if (element.navigation_type === 'custom') {
      return Boolean(!element.navigate_to_url)
    }
    return true
  }

  getDisplayName(element, applicationContext) {
    let displayValue = ''
    let destination = ''
    if (element.navigation_type === 'page') {
      const builder = applicationContext.builder

      const destinationPage = this.app.store.getters['page/getVisiblePages'](
        builder
      ).find(({ id }) => id === element.navigate_to_page_id)

      if (destinationPage) {
        destination = `${destinationPage.name}`
      }
    } else if (element.navigation_type === 'custom') {
      destination = ensureString(
        this.resolveFormula(element.navigate_to_url, applicationContext)
      ).trim()
    }

    if (destination) {
      destination = ` -> ${destination}`
    }

    if (element.value) {
      displayValue = ensureString(
        this.resolveFormula(element.value, applicationContext)
      ).trim()
    }

    return displayValue
      ? `${displayValue}${destination}`
      : `${this.name}${destination}`
  }
}

export class ImageElementType extends ElementType {
  static getType() {
    return 'image'
  }

  get name() {
    return this.app.i18n.t('elementType.image')
  }

  get description() {
    return this.app.i18n.t('elementType.imageDescription')
  }

  get iconClass() {
    return 'iconoir-media-image'
  }

  get component() {
    return ImageElement
  }

  get generalFormComponent() {
    return ImageElementForm
  }

  /**
   * Image element must have an image file or a URL as its source. Return true
   * to indicate an error when an image source doesn't exist, otherwise
   * return false.
   */
  isInError({ element }) {
    if (element.image_source_type === IMAGE_SOURCE_TYPES.UPLOAD) {
      return Boolean(!element.image_file?.url)
    } else {
      return Boolean(!element.image_url)
    }
  }

  getDisplayName(element, applicationContext) {
    if (element.alt_text) {
      const resolvedName = ensureString(
        this.resolveFormula(element.alt_text, applicationContext)
      ).trim()
      return resolvedName || this.name
    }
    return this.name
  }
}

export class ButtonElementType extends ElementType {
  static getType() {
    return 'button'
  }

  get name() {
    return this.app.i18n.t('elementType.button')
  }

  get description() {
    return this.app.i18n.t('elementType.buttonDescription')
  }

  get iconClass() {
    return 'iconoir-square-cursor'
  }

  get component() {
    return ButtonElement
  }

  get generalFormComponent() {
    return ButtonElementForm
  }

  getEvents(element) {
    return [new ClickEvent({ ...this.app })]
  }

  /**
   * A Button element must have a Workflow Action to be considered valid. Return
   * true if there are no Workflow Actions, otherwise return false.
   */
  isInError({ page, element }) {
    // If Button without any label should be considered invalid
    if (!element.value) {
      return true
    }

    const workflowActions = this.app.store.getters[
      'workflowAction/getElementWorkflowActions'
    ](page, element.id)

    return !workflowActions.length
  }

  getDisplayName(element, applicationContext) {
    if (element.value) {
      const resolvedName = ensureString(
        this.resolveFormula(element.value, applicationContext)
      ).trim()
      return resolvedName || this.name
    }
    return this.name
  }
}

export class ChoiceElementType extends FormElementType {
  static getType() {
    return 'choice'
  }

  get name() {
    return this.app.i18n.t('elementType.choice')
  }

  get description() {
    return this.app.i18n.t('elementType.choiceDescription')
  }

  get iconClass() {
    return 'iconoir-list-select'
  }

  get component() {
    return ChoiceElement
  }

  get generalFormComponent() {
    return ChoiceElementForm
  }

  formDataType(element) {
    return element.multiple ? 'array' : 'string'
  }

  getInitialFormDataValue(element, applicationContext) {
    try {
      if (element.multiple) {
        return ensureArray(
          this.resolveFormula(element.default_value, {
            element,
            ...applicationContext,
          })
        ).map(ensureStringOrInteger)
      } else {
        return ensureStringOrInteger(
          this.resolveFormula(element.default_value, {
            element,
            ...applicationContext,
          })
        )
      }
    } catch {
      return element.multiple ? [] : null
    }
  }

  getDisplayName(element, applicationContext) {
    const displayValue =
      element.label || element.default_value || element.placeholder

    if (displayValue) {
      const resolvedName = ensureString(
        this.resolveFormula(displayValue, applicationContext)
      ).trim()
      return resolvedName || this.name
    }
    return this.name
  }

  /**
   * Given a Choice Element, return an array of all valid option Values.
   *
   * When adding a new Option, the Page Designer can choose to only define the
   * Name and leave the Value undefined. In that case, the AB will assume the
   * Value to be the same as the Name. In the backend, the Value is stored as
   * null while the frontend visually displays the Name in its place.
   *
   * This means that an option's Value can sometimes be null. This method
   * gathers all valid Values. When a Value null, the Name is used instead.
   * Otherwise, the Value itself is used.
   *
   * @param element - The choice form element
   * @returns {Array} - An array of valid Values
   */
  choiceOptions(element) {
    return element.options.map((option) => {
      return option.value !== null ? option.value : option.name
    })
  }

  /**
   * Responsible for validating the choice form element. It behaves slightly
   * differently so that choice options with blank values are valid. We simply
   * test if the value is one of the choice's own values.
   * @param element - The choice form element
   * @param value - The value we are validating.
   * @param applicationContext - Required when using formula resolution.
   * @returns {boolean}
   */
  isValid(element, value, applicationContext) {
    const options =
      element.option_type === CHOICE_OPTION_TYPES.FORMULAS
        ? ensureArray(
            this.resolveFormula(element.formula_value, {
              element,
              ...applicationContext,
            })
          ).map(ensureStringOrInteger)
        : this.choiceOptions(element)

    const validOption = element.multiple
      ? options.some((option) => value.includes(option))
      : options.includes(value)

    return !(element.required && !validOption)
  }

  isInError({ element }) {
    switch (element.option_type) {
      case CHOICE_OPTION_TYPES.MANUAL:
        return element.options.length === 0
      case CHOICE_OPTION_TYPES.FORMULAS: {
        return element.formula_value === ''
      }
      default:
        return true
    }
  }

  getDataSchema(element) {
    const type = this.formDataType(element)
    if (type === 'string') {
      return {
        type: 'string',
      }
    } else if (type === 'array') {
      return {
        type: 'array',
        items: {
          type: 'string',
        },
      }
    }
  }
}

export class CheckboxElementType extends FormElementType {
  static getType() {
    return 'checkbox'
  }

  get name() {
    return this.app.i18n.t('elementType.checkbox')
  }

  get description() {
    return this.app.i18n.t('elementType.checkboxDescription')
  }

  get iconClass() {
    return 'iconoir-check'
  }

  get component() {
    return CheckboxElement
  }

  get generalFormComponent() {
    return CheckboxElementForm
  }

  formDataType(element) {
    return 'boolean'
  }

  getInitialFormDataValue(element, applicationContext) {
    try {
      return ensureBoolean(
        this.resolveFormula(element.default_value, {
          element,
          ...applicationContext,
        })
      )
    } catch {
      return false
    }
  }
}

export class IFrameElementType extends ElementType {
  static getType() {
    return 'iframe'
  }

  get name() {
    return this.app.i18n.t('elementType.iframe')
  }

  get description() {
    return this.app.i18n.t('elementType.iframeDescription')
  }

  get iconClass() {
    return 'iconoir-app-window'
  }

  get component() {
    return IFrameElement
  }

  get generalFormComponent() {
    return IFrameElementForm
  }

  /**
   * IFrame element must have a URL or an embedded value, depending on the
   * source_type. If the value doesn't exist, return true to indicate an error,
   * otherwise return false.
   */
  isInError({ element }) {
    if (element.source_type === IFRAME_SOURCE_TYPES.URL && !element.url) {
      return true
    } else if (
      element.source_type === IFRAME_SOURCE_TYPES.EMBED &&
      !element.embed
    ) {
      return true
    } else {
      return false
    }
  }

  getDisplayName(element, applicationContext) {
    if (element.url && element.url.length) {
      const resolvedName = ensureString(
        this.resolveFormula(element.url, applicationContext)
      )
      return resolvedName || this.name
    }
    return this.name
  }
}

export class RecordSelectorElementType extends CollectionElementTypeMixin(
  FormElementType
) {
  static getType() {
    return 'record_selector'
  }

  get fetchAtLoad() {
    return false
  }

  get name() {
    return this.app.i18n.t('elementType.recordSelector')
  }

  get description() {
    return this.app.i18n.t('elementType.recordSelectorDescription')
  }

  get iconClass() {
    return 'iconoir-select-window'
  }

  get component() {
    return RecordSelectorElement
  }

  get generalFormComponent() {
    return RecordSelectorElementForm
  }

  formDataType(element) {
    return element.multiple ? 'array' : 'number'
  }

  getInitialFormDataValue(element, applicationContext) {
    try {
      const resolvedFormula = this.resolveFormula(element.default_value, {
        ...applicationContext,
        element,
      })
      if (element.multiple) {
        return ensureArray(resolvedFormula).map(ensureInteger)
      } else {
        return ensureInteger(resolvedFormula)
      }
    } catch {
      return element.multiple ? [] : null
    }
  }

  getDisplayName(element, applicationContext) {
    const displayValue =
      element.label || element.default_value || element.placeholder

    if (displayValue) {
      const resolvedName = ensureString(
        this.resolveFormula(displayValue, applicationContext)
      ).trim()
      return resolvedName || this.name
    }
    return this.name
  }

  isValid(element, value, applicationContext) {
    if (!element.data_source_id) {
      return !element.required
    }

    if (element.required) {
      if (element.multiple && value.length === 0) {
        return false
      }
      if (!element.multiple && value === null) {
        return false
      }
    }

    return true
  }

  /**
   * This element is a special collection element. It's in error if it's data_source_id
   * is null.
   * @param {Object} element the element to check the error
   * @returns
   */
  isInError({ element }) {
    return !element.data_source_id
  }

  getDataSchema(element) {
    const type = this.formDataType(element)
    if (type === 'number') {
      return {
        type: 'number',
      }
    } else if (type === 'array') {
      return {
        type: 'array',
        items: {
          type: 'number',
        },
      }
    }
  }
}

export class DateTimePickerElementType extends FormElementType {
  static getType() {
    return 'datetime_picker'
  }

  get name() {
    return this.$t('elementType.dateTimePicker')
  }

  get description() {
    return this.$t('elementType.dateTimePickerDescription')
  }

  get iconClass() {
    return 'iconoir-calendar'
  }

  get component() {
    return DateTimePickerElement
  }

  get generalFormComponent() {
    return DateTimePickerElementForm
  }

  formDataType(element) {
    return element.include_time ? 'datetime' : 'date'
  }

  /**
   * Parse a date and time string value based on the element settings.
   * It uses element's `date_format` and `time_format` properties to parse the
   * date. It will only parse the time if `include_time` is on.
   *
   * @param element {Object} - The element that contains the formatting options.
   * @param value {string} - The date and time string to be parsed.
   * @returns {FormattedDate|FormattedDateTime} - The date or datetimme object.
   */
  parseElementDateTime(element, value) {
    const FormattedDateOrDateTimeClass = element.include_time
      ? FormattedDateTime
      : FormattedDate

    // Try to parse the date/datetime initially as an ISO string
    let parsedValue = new FormattedDateOrDateTimeClass(value)

    // If the previous fails, try again with the element current format
    if (!parsedValue.isValid()) {
      const dateFormat = DATE_FORMATS[element.date_format].format
      const timeFormat = TIME_FORMATS[element.time_format].format
      const format = element.include_time
        ? `${dateFormat} ${timeFormat}`
        : dateFormat
      parsedValue = new FormattedDateOrDateTimeClass(value, format)
    }
    return parsedValue
  }

  getInitialFormDataValue(element, applicationContext) {
    const resolvedDefaultValue = this.resolveFormula(element.default_value, {
      element,
      ...applicationContext,
    })
    return resolvedDefaultValue
      ? this.parseElementDateTime(element, resolvedDefaultValue)
      : null
  }

  isValid(element, value) {
    if (!value) {
      return !element.required
    }
    return this.parseElementDateTime(element, value).isValid()
  }
}

export class HeaderElementType extends MultiPageElementTypeMixin(
  ContainerElementTypeMixin(ElementType)
) {
  static getType() {
    return 'header'
  }

  get name() {
    return this.app.i18n.t('elementType.header')
  }

  get description() {
    return this.app.i18n.t('elementType.headerDescription')
  }

  get iconClass() {
    return 'iconoir-align-top-box'
  }

  get component() {
    return MultiPageContainerElement
  }

  get generalFormComponent() {
    return MultiPageContainerElementForm
  }

  getPagePlace() {
    return PAGE_PLACES.HEADER
  }

  getDefaultChildValues(page, values) {
    return {}
  }

  getDefaultValues(page, values) {
    const superValues = super.getDefaultValues(page, values)
    return {
      ...superValues,
      style_padding_left: 0,
      style_padding_right: 0,
    }
  }

  /**
   * We can't have this element inside another container. Not allowed outside of HEADER.
   * We can add id before the first element though.
   */
  isDisallowedReason({
    builder,
    page,
    parentElement,
    beforeElement,
    placeInContainer,
    pagePlace,
  }) {
    if (parentElement) {
      // Can't be inserted inside another container
      return this.app.i18n.t('elementType.notAllowedInsideContainer')
    }

    const sharedPage = this.app.store.getters['page/getSharedPage'](builder)

    if (
      page.id === sharedPage.id &&
      pagePlace &&
      pagePlace !== PAGE_PLACES.HEADER
    ) {
      // can't be inserted outside of header
      return this.app.i18n.t('elementType.notAllowedUnlessHeader')
    }

    if (page.id !== sharedPage.id) {
      const orderedElements =
        this.app.store.getters['element/getElementsOrdered'](page)
      // Can't be inserted after the first element of the page
      if (beforeElement && beforeElement.id !== orderedElements[0].id) {
        return this.app.i18n.t('elementType.notAllowedUnlessTop')
      }
    }
    return null
  }
}

export class FooterElementType extends HeaderElementType {
  static getType() {
    return 'footer'
  }

  getPagePlace() {
    return PAGE_PLACES.FOOTER
  }

  get name() {
    return this.app.i18n.t('elementType.footer')
  }

  get description() {
    return this.app.i18n.t('elementType.footerDescription')
  }

  get iconClass() {
    return 'iconoir-align-bottom-box'
  }

  get component() {
    return MultiPageContainerElement
  }

  get generalFormComponent() {
    return MultiPageContainerElementForm
  }

  /**
   * We can't have this element inside another container. Not allowed outside of FOOTER.
   * We can add id after the element of the page though.
   */
  isDisallowedReason({
    builder,
    page,
    parentElement,
    beforeElement,
    placeInContainer,
    pagePlace,
  }) {
    if (parentElement) {
      // Can't be inserted inside another container
      return this.app.i18n.t('elementType.notAllowedInsideContainer')
    }

    const sharedPage = this.app.store.getters['page/getSharedPage'](builder)
    if (
      page.id === sharedPage.id &&
      pagePlace &&
      pagePlace !== PAGE_PLACES.FOOTER
    ) {
      // can't be inserted outside of header
      return this.app.i18n.t('elementType.notAllowedUnlessFooter')
    }

    if (page.id !== sharedPage.id) {
      // Can't be inserted before the end of the page
      if (beforeElement && beforeElement.page_id !== sharedPage.id) {
        return this.app.i18n.t('elementType.notAllowedUnlessBottom')
      }
    }
    return null
  }
}
