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
  ensureNumeric,
  ensureInteger,
  ensurePositiveInteger,
  ensureString,
  ensureStringOrInteger,
  ensureDate,
  ensureDateTime,
} from '@baserow/modules/core/utils/validator'
import {
  CHOICE_OPTION_TYPES,
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
import SimpleContainerElement from '@baserow/modules/builder/components/elements/components/SimpleContainerElement.vue'
import SimpleContainerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/SimpleContainerElementForm.vue'
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
import MenuElement from '@baserow/modules/builder/components/elements/components/MenuElement'
import MenuElementForm from '@baserow/modules/builder/components/elements/components/forms/general/MenuElementForm'
import { pathParametersInError } from '@baserow/modules/builder/utils/params'
import {
  ContainerElementTypeMixin,
  CollectionElementTypeMixin,
  MultiPageElementTypeMixin,
} from '@baserow/modules/builder/elementTypeMixins'
import { isNumeric, isValidEmail } from '@baserow/modules/core/utils/string'

import {
  VISIBILITY_NOT_LOGGED,
  VISIBILITY_LOGGED_IN,
  ROLE_TYPE_ALLOW_EXCEPT,
  ROLE_TYPE_DISALLOW_EXCEPT,
} from '@baserow/modules/builder/constants'

import RatingElementForm from '@baserow/modules/builder/components/elements/components/forms/general/RatingElementForm'
import RatingElement from '@baserow/modules/builder/components/elements/components/RatingElement.vue'
import RatingInputElement from '@baserow/modules/builder/components/elements/components/RatingInputElement.vue'
import RatingInputElementForm from '@baserow/modules/builder/components/elements/components/forms/general/RatingInputElementForm.vue'

// Images for element modal
import elementImageButton from '@baserow/modules/builder/assets/icons/element-button.svg'
import elementImageChoice from '@baserow/modules/builder/assets/icons/element-choice.svg'
import elementImageCheckbox from '@baserow/modules/builder/assets/icons/element-checkbox.svg'
import elementImageColumn from '@baserow/modules/builder/assets/icons/element-column.svg'
import elementImageDatetimePicker from '@baserow/modules/builder/assets/icons/element-datetime_picker.svg'
import elementImageFooter from '@baserow/modules/builder/assets/icons/element-footer.svg'
import elementImageFormContainer from '@baserow/modules/builder/assets/icons/element-form_container.svg'
import elementImageHeader from '@baserow/modules/builder/assets/icons/element-header.svg'
import elementImageHeading from '@baserow/modules/builder/assets/icons/element-heading.svg'
import elementImageIFrame from '@baserow/modules/builder/assets/icons/element-iframe.svg'
import elementImageImage from '@baserow/modules/builder/assets/icons/element-image.svg'
import elementImageInputText from '@baserow/modules/builder/assets/icons/element-input_text.svg'
import elementImageLink from '@baserow/modules/builder/assets/icons/element-link.svg'
import elementImageMenu from '@baserow/modules/builder/assets/icons/element-menu.svg'
import elementImageRatingInput from '@baserow/modules/builder/assets/icons/element-rating_input.svg'
import elementImageRating from '@baserow/modules/builder/assets/icons/element-rating.svg'
import elementImageRecordSelector from '@baserow/modules/builder/assets/icons/element-record_selector.svg'
import elementImageRepeat from '@baserow/modules/builder/assets/icons/element-repeat.svg'
import elementImageSimpleContainer from '@baserow/modules/builder/assets/icons/element-simple_container.svg'
import elementImageTable from '@baserow/modules/builder/assets/icons/element-table.svg'
import elementImageText from '@baserow/modules/builder/assets/icons/element-text.svg'
import moment from '@baserow/modules/core/moment'

import _ from 'lodash'
import { getValueAtPath } from '../core/utils/object'

export class ElementType extends Registerable {
  get name() {
    return null
  }

  category() {
    return 'baseElement'
  }

  get description() {
    return null
  }

  get iconClass() {
    return null
  }

  get image() {
    throw new Error('image property must be implemented')
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
      'css_classes',
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
      'style_border_radius',
      'style_background_radius',
      'style_background',
      'style_background_color',
      'style_background_file',
      'style_background_mode',
      'style_width',
      'style_width_child',
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
    workspace,
    builder,
    page: destinationPage,
    parentElement,
    beforeElement,
    placeInContainer,
    pagePlace,
  }) {
    if (this.isDeactivatedReason({ workspace }) !== null) {
      return this.isDeactivatedReason({ workspace })
    }
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

  isDeactivatedReason({ workspace }) {
    return null
  }

  isDeactivated({ workspace }) {
    return !!this.isDeactivatedReason({ workspace })
  }

  getDeactivatedClickModal({ workspace }) {
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
   * @param {Object} applicationContext the applicationContext
   * @returns
   */
  isVisible({ element, applicationContext }) {
    const { builder } = applicationContext

    const user = this.app.store.getters['userSourceUser/getUser'](builder)
    const isAuthenticated =
      this.app.store.getters['userSourceUser/isAuthenticated'](builder)

    const { roles, role_type: roleType, visibility } = element

    if (visibility === VISIBILITY_LOGGED_IN) {
      if (!isAuthenticated) {
        return false
      }

      if (roleType === ROLE_TYPE_ALLOW_EXCEPT && roles.includes(user.role)) {
        return false
      }

      if (
        roleType === ROLE_TYPE_DISALLOW_EXCEPT &&
        !roles.includes(user.role)
      ) {
        return false
      }
    }

    if (visibility === VISIBILITY_NOT_LOGGED && isAuthenticated) {
      return false
    }

    if (
      element.visibility_condition?.formula &&
      !ensureBoolean(
        this.resolveFormula(element.visibility_condition, applicationContext),
        { useStrict: false }
      )
    ) {
      return false
    }

    return true
  }

  /**
   * If this element supports events, then this function will iterate over
   * them and ensure that they are configured properly. If they are in error,
   * this will propagate into an 'element in error' state.
   */
  workflowActionsInError(element, applicationContext) {
    const { builder } = applicationContext
    const elementPage = this.app.store.getters['page/getById'](
      builder,
      element.page_id
    )
    const workflowActions = this.app.store.getters[
      'builderWorkflowAction/getElementWorkflowActions'
    ](elementPage, element.id)

    return workflowActions.some((workflowAction) => {
      const workflowActionType = this.app.$registry.get(
        'workflowAction',
        workflowAction.type
      )
      return workflowActionType.isInError(workflowAction, applicationContext)
    })
  }

  /**
   * Returns the reason why the element configuration is invalid.
   * @param {object} param An object containing the workspace, page, element, and builder
   * @returns A string that represent the current error.
   */
  getErrorMessage(element, applicationContext) {
    const { workspace } = applicationContext

    if (this.isDeactivatedReason({ workspace }) !== null) {
      return this.isDeactivatedReason({ workspace })
    }

    if (
      this.getEvents(element).length > 0 &&
      this.workflowActionsInError(element, applicationContext)
    ) {
      return this.app.i18n.t('elementType.errorWorkflowActionInError')
    }

    return null
  }

  /**
   * Returns whether the element configuration is valid or not.
   * @param {object} param An object containing the page, element, and builder
   * @returns true if the element is in error
   */
  isInError(...params) {
    return Boolean(this.getErrorMessage(...params))
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
    return this.getCollectionAncestry({
      page,
      element,
      allowSameElement: false,
    }).map(({ id }) => id)
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
  uniqueElementId({ element, applicationContext }) {
    const {
      recordIndexPath,
      builder,
      page,
      allowSameElement = false,
    } = applicationContext

    const elementPage =
      element.page_id === page.id
        ? page
        : this.app.store.getters['page/getById'](builder, element.page_id)

    const collectionAncestorLength = this.getCollectionAncestry({
      page: elementPage,
      element,
      allowSameElement,
    }).length

    // We might be asking the uniqueID for an outside element so we don't
    // want to consume the whole record path
    const recordIndexPathForThisElement = (recordIndexPath || []).slice(
      0,
      collectionAncestorLength
    )

    return [element.id, ...recordIndexPathForThisElement].join('.')
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

  /**
   * Returns all collection ancestors of the given element. If allowSameElement is true,
   * also return the element itself if it's a collection element.
   * We get the right most chain of collection element starting from the first one
   * that has a data source.
   */
  getCollectionAncestry({ page, element, allowSameElement }) {
    const allCollectionAncestry = this.app.store.getters[
      'element/getAncestors'
    ](page, element, {
      predicate: (ancestor) =>
        this.app.$registry.get('element', ancestor.type).isCollectionElement,
      includeSelf: allowSameElement,
    })

    // Choose the right-most index of the ancestry which points
    // to a data source. If `allowSameElement` is `true`, this could
    // result in `element`'s `data_source_id`, rather than its parent
    // element's `data_source_id`.
    const lastIndex = _.findLastIndex(
      allCollectionAncestry,
      (ancestor) => ancestor.data_source_id !== null
    )

    return allCollectionAncestry.slice(lastIndex)
  }

  /**
   * Returns the current content (used by the current data provider) for the given
   * element. The content is extracted from the element with an actual data source
   * and refined using the current `recordIndexPath`, the schema properties of
   * intermediate collection element and finally the path given as parameter.
   */
  getElementCurrentContent(applicationContext, path = []) {
    const {
      builder,
      page,
      element,
      allowSameElement = true,
      // The default value is used when we try to resolve the name in element menu for
      // instance.
      recordIndexPath = [0],
    } = applicationContext

    const collectionAncestry = this.getCollectionAncestry({
      element,
      page,
      allowSameElement,
    })

    const mainElement = collectionAncestry[0] // The element with the data source

    if (
      !collectionAncestry.length ||
      !mainElement.data_source_id ||
      !collectionAncestry
        .slice(1)
        .every(({ schema_property: schemaProperty }) => schemaProperty)
    ) {
      return null
    }

    const mainElementType = this.app.$registry.get('element', mainElement.type)

    const mainDataSource = mainElementType.getDataSourceForElement({
      builder,
      page,
      element: mainElement,
    })

    if (!mainDataSource) {
      return null
    }

    const mainDataSourceType = this.app.$registry.get(
      'service',
      mainDataSource.type
    )

    // Create a path joining the record indexes and the schemaProperties
    const dataPaths = collectionAncestry
      .map(({ schema_property: schemaProperty }) => schemaProperty || null)
      .flatMap((x, i) =>
        i < recordIndexPath.length ? [x, recordIndexPath[i]] : [x]
      )
      .filter((v) => v !== null)

    const fullDataPath = [...dataPaths, ...path]

    const contentRows = mainElementType.getElementContentInStore(mainElement)

    if (fullDataPath.length) {
      let preparedPath
      if (mainDataSourceType.returnsList) {
        if (fullDataPath.length >= 2) {
          // not include the first path item as it's the row index
          // and the prepareValuePath is only able to support property level.
          const [row, ...rest] = fullDataPath
          preparedPath = [
            row,
            ...mainDataSourceType.prepareValuePath(mainDataSource, rest),
          ]
        } else {
          preparedPath = fullDataPath
        }
      } else {
        preparedPath = mainDataSourceType.prepareValuePath(
          mainDataSource,
          fullDataPath
        )
      }

      return getValueAtPath(contentRows, preparedPath)
    }

    return contentRows
  }
}

export class FormContainerElementType extends ContainerElementTypeMixin(
  ElementType
) {
  static getType() {
    return 'form_container'
  }

  category() {
    return 'formElement'
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

  get image() {
    return elementImageFormContainer
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
    workspace,
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
      workspace,
      builder,
      page,
      parentElement,
      beforeElement,
      placeInContainer,
      pagePlace,
    })
  }

  getEvents(element) {
    return [new SubmitEvent({ app: this.app })]
  }

  getErrorMessage(element, applicationContext) {
    const { builder } = applicationContext

    const elementPage = this.app.store.getters['page/getById'](
      builder,
      element.page_id
    )

    const workflowActions = this.app.store.getters[
      'builderWorkflowAction/getElementWorkflowActions'
    ](elementPage, element.id)

    if (!workflowActions.length) {
      return this.app.i18n.t('elementType.errorNoWorkflowAction')
    }

    return super.getErrorMessage(element, applicationContext)
  }
}

export class ColumnElementType extends ContainerElementTypeMixin(ElementType) {
  static getType() {
    return 'column'
  }

  category() {
    return 'layoutElement'
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

  get image() {
    return elementImageColumn
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
    workspace,
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
      workspace,
      builder,
      page,
      parentElement,
      beforeElement,
      placeInContainer,
      pagePlace,
    })
  }

  get childStylesForbidden() {
    return ['style_width', 'style_width_child']
  }

  get defaultPlaceInContainer() {
    return '0'
  }
}

export class SimpleContainerElementType extends ContainerElementTypeMixin(
  ElementType
) {
  static getType() {
    return 'simple_container'
  }

  category() {
    return 'layoutElement'
  }

  get name() {
    return this.app.i18n.t('elementType.simpleContainer')
  }

  get description() {
    return this.app.i18n.t('elementType.simpleContainerDescription')
  }

  get iconClass() {
    return 'iconoir-square'
  }

  get image() {
    return elementImageSimpleContainer
  }

  get component() {
    return SimpleContainerElement
  }

  get generalFormComponent() {
    return SimpleContainerElementForm
  }

  getDefaultValues(page, values) {
    const superValues = super.getDefaultValues(page, values)
    return {
      ...superValues,
      style_padding_left: 0,
      style_padding_right: 0,
      style_padding_top: 0,
      style_padding_bottom: 0,
    }
  }

  getDefaultChildValues(page, values) {
    // Unlike other container we don't want to affect the child padding.
    return {}
  }

  getElementPlaces(element) {
    return [null]
  }
}

export class TableElementType extends CollectionElementTypeMixin(ElementType) {
  static getType() {
    return 'table'
  }

  category() {
    return 'layoutElement'
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

  get image() {
    return elementImageTable
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
            app: this.app,
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
  getErrorMessage(element, applicationContext) {
    const { builder } = applicationContext

    const hasCollectionFieldInError = element.fields.some((collectionField) => {
      const collectionFieldType = this.app.$registry.get(
        'collectionField',
        collectionField.type
      )
      return collectionFieldType.isInError({
        field: collectionField,
        builder,
      })
    })

    if (hasCollectionFieldInError) {
      return this.app.i18n.t('elementType.errorCollectionFieldInError')
    }

    return super.getErrorMessage(element, applicationContext)
  }
}

export class RepeatElementType extends CollectionElementTypeMixin(
  ContainerElementTypeMixin(ElementType)
) {
  static getType() {
    return 'repeat'
  }

  category() {
    return 'layoutElement'
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

  get image() {
    return elementImageRepeat
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

  category() {
    return 'formElement'
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
    const resolvedName = ensureString(
      this.resolveFormula(element.label, applicationContext)
    ).trim()
    return resolvedName || this.name
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

  /**
   * Hook to pre process actionDispatchContext before it's used.
   * @param {Object} element the form element
   * @param {*} value the value of the actionDispatchContext
   * @param {Object} files a map that can be updated to add files to the payload of the
   *   action.
   */
  beforeActionDispatchContext(element, value, files) {
    return value
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

  get image() {
    return elementImageInputText
  }

  get component() {
    return InputTextElement
  }

  get generalFormComponent() {
    return InputTextElementForm
  }

  formDataType(element) {
    return element.validation_type === 'integer' ? 'number' : 'string'
  }

  getDisplayName(element, applicationContext) {
    const displayValue = element.label || element.placeholder
    const resolvedName = ensureString(
      this.resolveFormula(displayValue, applicationContext)
    ).trim()
    return resolvedName || this.name
  }

  getInitialFormDataValue(element, applicationContext) {
    try {
      const value = this.resolveFormula(element.default_value, {
        element,
        ...applicationContext,
      })

      return element.validation_type === 'integer'
        ? ensureNumeric(value, { allowNull: true })
        : ensureString(value)
    } catch {
      return null
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

  get image() {
    return elementImageHeading
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
  getErrorMessage(element, applicationContext) {
    if (!element.value.formula) {
      return this.app.i18n.t('elementType.errorValueMissing')
    }
    return super.getErrorMessage(element, applicationContext)
  }

  getDisplayName(element, applicationContext) {
    const resolvedName = ensureString(
      this.resolveFormula(element.value, applicationContext)
    ).trim()
    return resolvedName || this.name
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

  get image() {
    return elementImageText
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
  getErrorMessage(element, applicationContext) {
    if (!element.value.formula) {
      return this.app.i18n.t('elementType.errorValueMissing')
    }
    return super.getErrorMessage(element, applicationContext)
  }

  getDisplayName(element, applicationContext) {
    const resolvedName = ensureString(
      this.resolveFormula(element.value, applicationContext)
    ).trim()
    return resolvedName || this.name
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

  get image() {
    return elementImageLink
  }

  get component() {
    return LinkElement
  }

  get generalFormComponent() {
    return LinkElementForm
  }

  /**
   * When the Navigate To is a Page, the page and the path parameters must
   * be valid.
   *
   * When the Navigate To is a Custom URL, a Destination URL value must be
   * provided.
   */
  getErrorMessage(element, applicationContext) {
    const { builder } = applicationContext

    // A Link without any text isn't usable
    if (!element.value.formula) {
      return this.app.i18n.t('elementType.errorValueMissing')
    }

    if (element.navigation_type === 'page') {
      if (!element.navigate_to_page_id) {
        return this.app.i18n.t('elementType.errorNavigateToPageMissing')
      }
      if (
        pathParametersInError(
          element,
          this.app.store.getters['page/getVisiblePages'](builder)
        )
      ) {
        return this.app.i18n.t('elementType.errorPageParameterInError')
      }
    } else if (
      element.navigation_type === 'custom' &&
      !element.navigate_to_url.formula
    ) {
      return this.app.i18n.t('elementType.errorNavigationUrlMissing')
    }
    return super.getErrorMessage(element, applicationContext)
  }

  getDisplayName(element, applicationContext) {
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

    const displayValue = ensureString(
      this.resolveFormula(element.value, applicationContext)
    ).trim()

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

  get image() {
    return elementImageImage
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
  getErrorMessage(element, applicationContext) {
    if (
      element.image_source_type === IMAGE_SOURCE_TYPES.UPLOAD &&
      !element.image_file?.url
    ) {
      return this.app.i18n.t('elementType.errorImageFileMissing')
    } else if (
      element.image_source_type === IMAGE_SOURCE_TYPES.URL &&
      !element.image_url
    ) {
      return this.app.i18n.t('elementType.errorImageUrlMissing')
    }
    return super.getErrorMessage(element, applicationContext)
  }

  getDisplayName(element, applicationContext) {
    const resolvedName = ensureString(
      this.resolveFormula(element.alt_text, applicationContext)
    ).trim()
    return resolvedName || this.name
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

  get image() {
    return elementImageButton
  }

  get component() {
    return ButtonElement
  }

  get generalFormComponent() {
    return ButtonElementForm
  }

  getEvents(element) {
    return [new ClickEvent({ app: this.app })]
  }

  /**
   * A Button element must have a Workflow Action to be considered valid. Return
   * true if there are no Workflow Actions, otherwise return false.
   */
  getErrorMessage(element, applicationContext) {
    const { builder } = applicationContext
    // If Button without any label should be considered invalid
    if (!element.value.formula) {
      return this.app.i18n.t('elementType.errorValueMissing')
    }
    const elementPage = this.app.store.getters['page/getById'](
      builder,
      element.page_id
    )

    const workflowActions = this.app.store.getters[
      'builderWorkflowAction/getElementWorkflowActions'
    ](elementPage, element.id)

    if (!workflowActions.length) {
      return this.app.i18n.t('elementType.errorNoWorkflowAction')
    }

    return super.getErrorMessage(element, applicationContext)
  }

  getDisplayName(element, applicationContext) {
    const resolvedName = ensureString(
      this.resolveFormula(element.value, applicationContext)
    ).trim()
    return resolvedName || this.name
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

  get image() {
    return elementImageChoice
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
  getOptionsResolved(element, applicationContext) {
    switch (element.option_type) {
      case CHOICE_OPTION_TYPES.MANUAL:
        return element.options.map(({ name, value }) => ({
          name,
          value: value === null ? name : value,
        }))
      case CHOICE_OPTION_TYPES.FORMULAS: {
        const formulaValues = ensureArray(
          this.resolveFormula(element.formula_value, applicationContext)
        )
        const formulaNames = ensureArray(
          this.resolveFormula(element.formula_name, applicationContext)
        )
        return formulaValues.map((value, index) => ({
          id: index,
          value: ensureStringOrInteger(value),
          name: ensureString(
            index < formulaValues.length ? formulaNames[index] : value
          ),
        }))
      }
      default:
        return []
    }
  }

  getInitialFormDataValue(element, applicationContext) {
    let converter = ensureString
    const optionsResolved = this.getOptionsResolved(element, applicationContext)

    const firstOption = optionsResolved.find(
      ({ value }) => value !== undefined && value !== null // We skip null values
    )

    if (firstOption && Number.isInteger(firstOption.value)) {
      converter = (v) => ensurePositiveInteger(v, { allowNull: true })
    }

    if (element.multiple) {
      try {
        const existingValues = optionsResolved.map(({ value }) => value)
        return ensureArray(
          this.resolveFormula(element.default_value, applicationContext)
        )
          .map(converter)
          .filter((value) => existingValues.includes(value))
      } catch {
        return []
      }
    } else {
      try {
        // Always return a string if we have a default value, otherwise
        // set the value to null as single select fields will only skip
        // field preparation if the value is null.
        const resolvedSingleValue = converter(
          this.resolveFormula(element.default_value, applicationContext)
        )
        return resolvedSingleValue === '' ? null : resolvedSingleValue
      } catch {
        return null
      }
    }
  }

  getDisplayName(element, applicationContext) {
    const displayValue = element.label || element.placeholder
    const resolvedName = ensureString(
      this.resolveFormula(displayValue, applicationContext)
    ).trim()
    return resolvedName || this.name
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
    const optionValues = this.getOptionsResolved(
      element,
      applicationContext
    ).map(({ value }) => value)

    const validOption = element.multiple
      ? optionValues.some((option) => value.includes(option))
      : optionValues.includes(value)

    return !(element.required && !validOption)
  }

  getErrorMessage(element, applicationContext) {
    if (element.option_type === CHOICE_OPTION_TYPES.MANUAL) {
      if (element.options.length === 0) {
        return this.app.i18n.t('elementType.errorOptionsMissing')
      }
    } else if (element.option_type === CHOICE_OPTION_TYPES.FORMULAS) {
      if (element.formula_value === '') {
        return this.app.i18n.t('elementType.errorOptionsMissing')
      }
    }
    return super.getErrorMessage(element, applicationContext)
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

  get image() {
    return elementImageCheckbox
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

  get image() {
    return elementImageIFrame
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
  getErrorMessage(element, applicationContext) {
    if (
      element.source_type === IFRAME_SOURCE_TYPES.URL &&
      !element.url.formula
    ) {
      return this.app.i18n.t('elementType.errorIframeUrlMissing')
    } else if (
      element.source_type === IFRAME_SOURCE_TYPES.EMBED &&
      !element.embed.formula
    ) {
      return this.app.i18n.t('elementType.errorIframeContentMissing')
    }
    return super.getErrorMessage(element, applicationContext)
  }

  getDisplayName(element, applicationContext) {
    const resolvedName = ensureString(
      this.resolveFormula(element.url, applicationContext)
    )
    return resolvedName || this.name
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

  get image() {
    return elementImageRecordSelector
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
    const displayValue = element.label || element.placeholder
    const resolvedName = ensureString(
      this.resolveFormula(displayValue, applicationContext)
    ).trim()
    return resolvedName || this.name
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
  getErrorMessage(element, applicationContext) {
    if (!element.data_source_id) {
      return this.$t('elementType.errorDataSourceMissing')
    }
    return super.getErrorMessage(element, applicationContext)
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

  get image() {
    return elementImageDatetimePicker
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

  getInitialFormDataValue(element, applicationContext) {
    const resolvedDefaultValue = this.resolveFormula(element.default_value, {
      element,
      ...applicationContext,
    })

    if (!resolvedDefaultValue) {
      return null
    }

    try {
      // We try to convert it to a date and if it works we return it.
      const result = element.include_time
        ? ensureDateTime(resolvedDefaultValue)
        : ensureDate(resolvedDefaultValue)

      if (result && !isNaN(result)) {
        // We convert to an iso string here because date objects are not serialized
        // properly during SSR
        return result.toJSON()
      } else {
        return result
      }
    } catch (e) {
      return null
    }
  }

  isValid(element, value) {
    if (!value) {
      return !element.required
    }

    if (typeof value === 'string') {
      // During SSR the date object becomes a string so we need to check
      // that as well
      const date = moment(value)
      if (date.isValid()) {
        return true
      }
    }

    return value instanceof Date && !isNaN(value)
  }
}

export class HeaderElementType extends MultiPageElementTypeMixin(
  ContainerElementTypeMixin(ElementType)
) {
  static getType() {
    return 'header'
  }

  category() {
    return 'layoutElement'
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

  get image() {
    return elementImageHeader
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
    workspace,
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

  category() {
    return 'layoutElement'
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

  get image() {
    return elementImageFooter
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
    workspace,
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

export class RatingInputElementType extends FormElementType {
  static getType() {
    return 'rating_input'
  }

  get name() {
    return this.app.i18n.t('elementType.ratingInput')
  }

  get description() {
    return this.app.i18n.t('elementType.ratingInputDescription')
  }

  get iconClass() {
    return 'iconoir-bubble-star'
  }

  get image() {
    return elementImageRatingInput
  }

  get component() {
    return RatingInputElement
  }

  get generalFormComponent() {
    return RatingInputElementForm
  }

  formDataType(element) {
    return 'number'
  }

  getInitialFormDataValue(element, applicationContext) {
    try {
      return ensurePositiveInteger(
        this.resolveFormula(element.value, {
          element,
          ...applicationContext,
        })
      )
    } catch {
      return 0
    }
  }

  isValid(element, value) {
    if (element.required && (value === null || value === undefined)) {
      return false
    }
    return value >= 0 && value <= element.max_value
  }
}

export class RatingElementType extends ElementType {
  static getType() {
    return 'rating'
  }

  get name() {
    return this.app.i18n.t('elementType.rating')
  }

  get description() {
    return this.app.i18n.t('elementType.ratingDescription')
  }

  get iconClass() {
    return 'iconoir-leaderboard-star'
  }

  get image() {
    return elementImageRating
  }

  get component() {
    return RatingElement
  }

  get generalFormComponent() {
    return RatingElementForm
  }
}

export class MenuElementType extends ElementType {
  static getType() {
    return 'menu'
  }

  get name() {
    return this.app.i18n.t('elementType.menu')
  }

  get description() {
    return this.app.i18n.t('elementType.menuDescription')
  }

  get iconClass() {
    return 'iconoir-menu'
  }

  get image() {
    return elementImageMenu
  }

  get component() {
    return MenuElement
  }

  get generalFormComponent() {
    return MenuElementForm
  }

  getEventByName(element, name) {
    return this.getEvents(element).find((event) => event.name === name)
  }

  getEvents(element) {
    return (element.menu_items || [])
      .map((item) => {
        const { type: menuItemType, name, uid } = item
        if (menuItemType === 'button') {
          return [
            new ClickEvent({
              app: this.app,
              namePrefix: uid,
              labelSuffix: `- ${name}`,
              applicationContextAdditions: { allowSameElement: true },
            }),
          ]
        }
        return []
      })
      .flat()
  }

  getErrorMessage(element, applicationContext) {
    const { builder } = applicationContext
    // There must be at least one menu item
    if (!element.menu_items?.length) {
      return this.app.i18n.t('elementType.errorNoMenuItem')
    }

    const elementPage = this.app.store.getters['page/getById'](
      builder,
      element.page_id
    )

    if (
      element.menu_items.some((menuItem) => {
        return this.getItemMenuError({
          builder,
          elementPage,
          element,
          menuItem,
        })
      })
    ) {
      return this.app.i18n.t('elementType.errorMenuItemInError')
    }

    return super.getErrorMessage(element, applicationContext)
  }

  getItemMenuError({ builder, elementPage, element, menuItem }) {
    const workflowActions = this.app.store.getters[
      'builderWorkflowAction/getElementWorkflowActions'
    ](elementPage, element.id)

    if (menuItem.children?.length) {
      if (
        menuItem.children.some((child) => {
          return this.menuItemErrorMessage(child, builder, workflowActions)
        })
      ) {
        return this.app.i18n.t('elementType.errorSubMenuItemInError')
      }
    } else {
      return this.menuItemErrorMessage(menuItem, builder, workflowActions)
    }
    return null
  }

  menuItemErrorMessage(menuItem, builder, workflowActions) {
    switch (menuItem.type) {
      case 'separator':
      case 'spacer':
        return null
      case 'button':
        if (!menuItem.name) {
          return this.app.i18n.t('elementType.errorNameMissing')
        }
        if (!workflowActions.length) {
          return this.app.i18n.t('elementType.errorNoWorkflowAction')
        }
        break
      case 'link':
        if (!menuItem.name) {
          return this.app.i18n.t('elementType.errorNameMissing')
        }

        if (!menuItem.children?.length) {
          if (menuItem.navigation_type === 'page') {
            if (!menuItem.navigate_to_page_id) {
              return this.app.i18n.t('elementType.errorNavigateToPageMissing')
            }
            if (
              pathParametersInError(
                menuItem,
                this.app.store.getters['page/getVisiblePages'](builder)
              )
            ) {
              return this.app.i18n.t('elementType.errorPageParameterInError')
            }
          }

          if (
            menuItem.navigation_type === 'custom' &&
            !menuItem.navigate_to_url.formula
          ) {
            return this.app.i18n.t('elementType.errorNavigationUrlMissing')
          }
        }
        break
    }

    return null
  }

  getDisplayName(element, applicationContext) {
    return this.name
  }
}
