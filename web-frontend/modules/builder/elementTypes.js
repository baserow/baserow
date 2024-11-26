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
  ELEMENT_EVENTS,
  PLACEMENTS,
  TIME_FORMATS,
  IMAGE_SOURCE_TYPES,
  IFRAME_SOURCE_TYPES,
} from '@baserow/modules/builder/enums'
import ColumnElement from '@baserow/modules/builder/components/elements/components/ColumnElement'
import ColumnElementForm from '@baserow/modules/builder/components/elements/components/forms/general/ColumnElementForm'
import _ from 'lodash'
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
import { pathParametersInError } from '@baserow/modules/builder/utils/params'
import { isNumeric, isValidEmail } from '@baserow/modules/core/utils/string'
import RecordSelectorElementForm from '@baserow/modules/builder/components/elements/components/forms/general/RecordSelectorElementForm.vue'
import DateTimePickerElement from '@baserow/modules/builder/components/elements/components/DateTimePickerElement.vue'
import DateTimePickerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/DateTimePickerElementForm.vue'
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
   * Move a component in the same place.
   * @param {Object} page - The page the element belongs to
   * @param {Object} element - The element to move
   * @param {String} placement - The direction of the move
   */
  async moveElementInSamePlace(page, element, placement) {
    let beforeElementId = null

    switch (placement) {
      case PLACEMENTS.BEFORE: {
        const previousElement = this.app.store.getters[
          'element/getPreviousElement'
        ](page, element)

        beforeElementId = previousElement ? previousElement.id : null
        break
      }
      case PLACEMENTS.AFTER: {
        const nextElement = this.app.store.getters['element/getNextElement'](
          page,
          element
        )

        if (nextElement) {
          const nextNextElement = this.app.store.getters[
            'element/getNextElement'
          ](page, nextElement)
          beforeElementId = nextNextElement ? nextNextElement.id : null
        }
        break
      }
    }

    await this.app.store.dispatch('element/move', {
      page,
      elementId: element.id,
      beforeElementId,
      parentElementId: element.parent_element_id
        ? element.parent_element_id
        : null,
      placeInContainer: element.place_in_container,
    })
  }

  /**
   * Move an element according to the new placement.
   * @param {Object} page - The page the element belongs to
   * @param {Object} element - The element to move
   * @param {String} placement - The direction of the move
   */
  async moveElement(page, element, placement) {
    if (element.parent_element_id !== null) {
      const parentElement = this.app.store.getters['element/getElementById'](
        page,
        element.parent_element_id
      )

      const parentElementType = this.app.$registry.get(
        'element',
        parentElement.type
      )
      await parentElementType.moveChildElement(
        page,
        parentElement,
        element,
        placement
      )
    } else {
      await this.moveElementInSamePlace(page, element, placement)
    }
  }

  /**
   * Identify and select the next element according to the new placement.
   *
   * @param {Object} page - The page the element belongs to
   * @param {Object} element - The element on which the selection should be based on
   * @param {String} placement - The direction of the selection
   */
  async selectNextElement(page, element, placement) {
    let elementToBeSelected = null
    if (placement === PLACEMENTS.BEFORE) {
      elementToBeSelected = this.app.store.getters[
        'element/getPreviousElement'
      ](page, element)
    } else if (placement === PLACEMENTS.AFTER) {
      elementToBeSelected = this.app.store.getters['element/getNextElement'](
        page,
        element
      )
    } else {
      const containerElement = this.app.store.getters['element/getElementById'](
        page,
        element.parent_element_id
      )
      const containerElementType = this.app.$registry.get(
        'element',
        containerElement.type
      )
      elementToBeSelected =
        containerElementType.getNextHorizontalElementToSelect(
          page,
          element,
          placement
        )
    }

    if (!elementToBeSelected) {
      return
    }

    try {
      await this.app.store.dispatch('element/select', {
        element: elementToBeSelected,
      })
    } catch {}
  }

  /**
   * Returns vertical placement disabled.
   * @param {Object} page - The page the element belongs to
   * @param {Object} element - The element to move
   * @param {String} placement - The direction of the move
   */
  getVerticalPlacementsDisabled(page, element) {
    const previousElement = this.app.store.getters[
      'element/getPreviousElement'
    ](page, element)
    const nextElement = this.app.store.getters['element/getNextElement'](
      page,
      element
    )

    const placementsDisabled = []

    if (!previousElement) {
      placementsDisabled.push(PLACEMENTS.BEFORE)
    }

    if (!nextElement) {
      placementsDisabled.push(PLACEMENTS.AFTER)
    }

    return placementsDisabled
  }

  /**
   * Return an array of placements that are disallowed for the element to move
   * in their container (or root page).
   *
   * @param {Object} page The page that is the parent component.
   * @param {Number} element The element for which the placements should be
   *  calculated.
   * @returns {Array} An array of placements that are disallowed for the element.
   */
  getPlacementsDisabled(page, element) {
    // If the element has a parent, let the parent container type derive the
    // disabled placements.
    if (element.parent_element_id) {
      const containerElement = this.app.store.getters['element/getElementById'](
        page,
        element.parent_element_id
      )
      const elementType = this.app.$registry.get(
        'element',
        containerElement.type
      )
      return elementType.getPlacementsDisabledForChild(
        page,
        containerElement,
        element
      )
    }

    return [
      PLACEMENTS.LEFT,
      PLACEMENTS.RIGHT,
      ...this.getVerticalPlacementsDisabled(page, element),
    ]
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
   * Given an element, iterates over the element's ancestors and finds the
   * first collection element. An optional function can be passed to map over
   * each ancestor element.
   *
   * @param {Object} page - The page the element belongs to.
   * @param {Object} element - The element to start the search from.
   * @param {Function} ancestorMapFn - An optional function which will be
   * called for each ancestor element, after ensuring it's a collection element.
   */
  firstCollectionAncestor(page, element, ancestorMapFn = (element) => true) {
    const elementType = this.app.$registry.get('element', element.type)
    if (elementType.isCollectionElement && ancestorMapFn(element)) {
      return element
    }
    const ancestors = this.app.store.getters['element/getAncestors'](
      page,
      element
    )
    for (const ancestor of ancestors) {
      const ancestorType = this.app.$registry.get('element', ancestor.type)
      if (ancestorType.isCollectionElement && ancestorMapFn(ancestor)) {
        return ancestor
      }
    }
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

const ContainerElementTypeMixin = (Base) =>
  class extends Base {
    isContainerElement = true

    get elementTypesAll() {
      return Object.values(this.app.$registry.getAll('element'))
    }

    /**
     * Returns an array of element types that are not allowed as children of this element type.
     * @param {object} page - The page the element belongs to.
     * @param {Object} element The element in question, it can be used to
     *  determine in a more dynamic way if specific children are permitted.
     * @returns {Array} An array of forbidden child element types.
     */
    childElementTypesForbidden(page, element) {
      return []
    }

    /**
     * Returns an array of element types that are allowed as children of this element.
     * If the parent element we're trying to add a child to has a parent, we'll check
     * each parent until the root element if they have any forbidden element types to
     * include as well.
     * @param page
     * @param element
     * @returns {Array} An array of permitted child element types.
     */
    childElementTypes(page, element) {
      if (element.parent_element_id) {
        const parentElement = this.app.store.getters['element/getElementById'](
          page,
          element.parent_element_id
        )
        const parentElementType = this.app.$registry.get(
          'element',
          parentElement.type
        )
        return _.difference(
          parentElementType.childElementTypes(page, parentElement),
          this.childElementTypesForbidden(page, element)
        )
      }
      return _.difference(
        this.elementTypesAll,
        this.childElementTypesForbidden(page, element)
      )
    }

    /**
     * Returns an array of style types that are not allowed as children of this element.
     * @returns {Array}
     */
    get childStylesForbidden() {
      return []
    }

    get defaultPlaceInContainer() {
      throw new Error('Not implemented')
    }

    /**
     * Returns the default value when creating a child element to this container.
     * @param {Object} page The current page object
     * @param {Object} values The values of the to be created element
     * @returns the default values for this element.
     */
    getDefaultChildValues(page, values) {
      // By default, an element inside a container should have no left and right padding
      return { style_padding_left: 0, style_padding_right: 0 }
    }

    /**
     * Given a `page` and an `element`, move the child element of a container
     * in the direction specified by the `placement`.
     *
     * The default implementation only supports moving the element vertically.
     *
     * @param {Object} page The page that is the parent component.
     * @param {Number} element The child element to be moved.
     * @param {String} placement The direction in which the element should move.
     */
    async moveChildElement(page, parentElement, element, placement) {
      if (placement === PLACEMENTS.AFTER || placement === PLACEMENTS.BEFORE) {
        await this.moveElementInSamePlace(page, element, placement)
      }
    }

    /**
     * Return an array of placements that are disallowed for the elements to move
     * in their container.
     *
     * @param {Object} page The page that is the parent component.
     * @param {Number} element The child element for which the placements should
     *    be calculated.
     * @returns {Array} An array of placements that are disallowed for the element.
     */
    getPlacementsDisabledForChild(page, containerElement, element) {
      this.getPlacementsDisabled(page, element)
    }

    getNextHorizontalElementToSelect(page, element, placement) {
      return null
    }

    /**
     * A Container element without any child elements is invalid. Return true
     * if there are no children, otherwise return false.
     */
    isInError({ page, element }) {
      const children = this.app.store.getters['element/getChildren'](
        page,
        element
      )

      return !children.length
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

  /**
   * Only disallow form containers as nested elements.
   * @param {object} page - The page the element belongs to.
   * @param {Object} element The element in question, it can be used to
   *  determine in a more dynamic way if specific children are permitted.
   * @returns {Array} An array containing the `FormContainerElementType`.
   */
  childElementTypesForbidden(page, element) {
    return this.elementTypesAll.filter(
      (elementType) => elementType.type === this.getType()
    )
  }

  get childStylesForbidden() {
    return ['style_width']
  }

  getEvents(element) {
    return [new SubmitEvent({ ...this.app })]
  }

  /**
   * Return an array of placements that are disallowed for the elements to move
   * in their container.
   *
   * @param {Object} page The page that is the parent component.
   * @param {Number} element The child element for which the placements should
   *    be calculated.
   * @returns {Array} An array of placements that are disallowed for the element.
   */
  getPlacementsDisabledForChild(page, containerElement, element) {
    return [
      PLACEMENTS.LEFT,
      PLACEMENTS.RIGHT,
      ...this.getVerticalPlacementsDisabled(page, element),
    ]
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

  /**
   * Only disallow column elements as nested elements.
   * @param {object} page - The page the element belongs to.
   * @param {Object} element The element in question, it can be used to
   *  determine in a more dynamic way if specific children are permitted.
   * @returns {Array} An array containing the `ColumnElementType`.
   */
  childElementTypesForbidden(page, element) {
    return this.elementTypesAll.filter(
      (elementType) => elementType.type === this.getType()
    )
  }

  get childStylesForbidden() {
    return ['style_width']
  }

  get defaultPlaceInContainer() {
    return '0'
  }

  /**
   * Given a `page` and an `element`, move the child element of a container
   * in the direction specified by the `placement`.
   *
   * @param {Object} page The page that is the parent component.
   * @param {Number} element The child element to be moved.
   * @param {String} placement The direction in which the element should move.
   */
  async moveChildElement(page, parentElement, element, placement) {
    if (placement === PLACEMENTS.AFTER || placement === PLACEMENTS.BEFORE) {
      await super.moveChildElement(page, parentElement, element, placement)
    } else {
      const placeInContainer = parseInt(element.place_in_container)
      const newPlaceInContainer =
        placement === PLACEMENTS.LEFT
          ? placeInContainer - 1
          : placeInContainer + 1

      if (newPlaceInContainer >= 0) {
        await this.app.store.dispatch('element/move', {
          page,
          elementId: element.id,
          beforeElementId: null,
          parentElementId: parentElement.id,
          placeInContainer: `${newPlaceInContainer}`,
        })
      }
    }
  }

  /**
   * Return an array of placements that are disallowed for the elements to move
   * in their container.
   *
   * @param {Object} page The page that is the parent component.
   * @param {Number} element The child element for which the placements should
   *    be calculated.
   * @returns {Array} An array of placements that are disallowed for the element.
   */
  getPlacementsDisabledForChild(page, containerElement, element) {
    const columnIndex = parseInt(element.place_in_container)

    const placementsDisabled = []

    if (columnIndex === 0) {
      placementsDisabled.push(PLACEMENTS.LEFT)
    }

    if (columnIndex === containerElement.column_amount - 1) {
      placementsDisabled.push(PLACEMENTS.RIGHT)
    }

    return [
      ...placementsDisabled,
      ...this.getVerticalPlacementsDisabled(page, element),
    ]
  }

  getNextHorizontalElementToSelect(page, element, placement) {
    const offset = placement === PLACEMENTS.LEFT ? -1 : 1
    const containerElement = this.app.store.getters['element/getElementById'](
      page,
      element.parent_element_id
    )

    let elementsInPlace = []
    let nextPlaceInContainer = parseInt(element.place_in_container)
    for (let i = 0; i < containerElement.column_amount; i++) {
      nextPlaceInContainer += offset
      elementsInPlace = this.app.store.getters['element/getElementsInPlace'](
        page,
        containerElement.id,
        nextPlaceInContainer.toString()
      )

      if (elementsInPlace.length) {
        return elementsInPlace[elementsInPlace.length - 1]
      }
    }

    return null
  }
}

const CollectionElementTypeMixin = (Base) =>
  class extends Base {
    isCollectionElement = true

    /**
     * A helper function responsible for returning this collection element's
     * schema properties.
     */
    getSchemaProperties(dataSource) {
      const serviceType = this.app.$registry.get('service', dataSource.type)
      const schema = serviceType.getDataSchema(dataSource)
      if (!schema) {
        return []
      }
      return schema.type === 'array'
        ? schema.items.properties
        : schema.properties
    }

    /**
     * Given a schema property name, is responsible for finding the matching
     * property option in the element. If it doesn't exist, then we return
     * an empty object, and it won't be included in the adhoc header.
     * @param {object} element - the element we want to extract options from.
     * @param {string} schemaProperty - the schema property name to check.
     * @returns {object} - the matching property option, or an empty object.
     */
    getPropertyOptionsByProperty(element, schemaProperty) {
      return (
        element.property_options.find((option) => {
          return option.schema_property === schemaProperty
        }) || {}
      )
    }

    /**
     * Responsible for iterating over the schema's properties, filtering
     * the results down to the properties which are `filterable`, `sortable`,
     * and `searchable`, and then returning the property value.
     * @param {string} option - the `filterable`, `sortable` or `searchable`
     *  property option. If the value is `true` then the property will be
     *  included in the adhoc header component.
     * @param {object} element - the element we want to extract options from.
     * @param {object} dataSource - the dataSource used by `element`.
     * @returns {array} - an array of schema properties which are present
     *  in the element's property options where `option` = `true`.
     */
    getPropertyOptionByType(option, element, dataSource) {
      const schemaProperties = dataSource
        ? this.getSchemaProperties(dataSource)
        : []
      return Object.entries(schemaProperties)
        .filter(
          ([schemaProperty, _]) =>
            this.getPropertyOptionsByProperty(element, schemaProperty)[
              option
            ] || false
        )
        .map(([_, property]) => property)
    }

    /**
     * An array of properties within this element which have been flagged
     * as filterable by the page designer.
     */
    adhocFilterableProperties(element, dataSource) {
      return this.getPropertyOptionByType('filterable', element, dataSource)
    }

    /**
     * An array of properties within this element which have been flagged
     * as sortable by the page designer.
     */
    adhocSortableProperties(element, dataSource) {
      return this.getPropertyOptionByType('sortable', element, dataSource)
    }

    /**
     * An array of properties within this element which have been flagged
     * as searchable by the page designer.
     */
    adhocSearchableProperties(element, dataSource) {
      return this.getPropertyOptionByType('searchable', element, dataSource)
    }

    /**
     * By default collection element will load their content at loading time
     * but if you don't want that you can return false here.
     */
    get fetchAtLoad() {
      return true
    }

    hasCollectionAncestor(page, element) {
      return this.app.store.getters['element/getAncestors'](page, element).some(
        ({ type }) => {
          const ancestorType = this.app.$registry.get('element', type)
          return ancestorType.isCollectionElement
        }
      )
    }

    /**
     * A simple check to return whether this collection element has a
     * "source of data" (i.e. a data source, or a schema property).
     * Should not be used as an "in error" or validation check, use
     * `isInError` for this purpose as it is more thorough.
     * @param element - The element we want to check for a source of data.
     * @returns {Boolean} - Whether the element has a source of data.
     */
    hasSourceOfData(element) {
      return Boolean(element.data_source_id || element.schema_property)
    }

    /**
     * Collection elements by default will have three permutations of display names:
     *
     * 1. If no data source exists, on `element` or its ancestors, then:
     *   - "Repeat" is returned.
     * 2. If a data source is found, and `element` has no `schema_property`, then:
     *   - "Repeat {dataSourceName}" is returned.
     * 3. If a data source is found, `element` has a `schema_property`, and the integration is Baserow, then:
     *   - "Repeat {schemaPropertyTitle} ({fieldTypeName})" is returned
     * 4. If a data source is found, `element` has a `schema_property`, and the integration isn't Baserow, then:
     *   - "Repeat {schemaPropertyTitle}" is returned
     * @param element - The element we want to get a display name for.
     * @param page - The page the element belongs to.
     * @returns {string} - The display name for the element.
     */
    getDisplayName(element, { page, builder }) {
      let suffix = ''

      const collectionAncestors = this.app.store.getters[
        'element/getAncestors'
      ](page, element, {
        predicate: (ancestor) =>
          this.app.$registry.get('element', ancestor.type)
            .isCollectionElement && ancestor.data_source_id !== null,
      })

      // If the collection element has ancestors, pluck out the first one, which
      // will have a data source. Otherwise, use `element`, as this element is
      // the root level element.
      const collectionElement = collectionAncestors.length
        ? collectionAncestors[0]
        : element

      // If we find a collection ancestor which has a data source, we'll
      // use the data source's name as part of the display name.
      if (collectionElement?.data_source_id) {
        const sharedPage = this.app.store.getters['page/getSharedPage'](builder)
        const dataSource = this.app.store.getters[
          'dataSource/getPagesDataSourceById'
        ]([page, sharedPage], collectionElement?.data_source_id)
        suffix = dataSource ? dataSource.name : ''

        // If we have a data source, and the element has a schema property,
        // we'll find the property within the data source's schema and pluck
        // out the title property.
        if (element.schema_property) {
          // Find the schema properties. They'll be in different places,
          // depending on whether this is a list or single row data source.
          const schemaProperties =
            dataSource.schema.type === 'array'
              ? dataSource.schema?.items?.properties
              : dataSource.schema.properties
          const schemaField = schemaProperties[element.schema_property]
          // Only Local/Remote Baserow table schemas will have `original_type`,
          // which is the `FieldType`. If we find it, we can use it to display
          // what kind of field type was used.
          suffix = schemaField?.title || element.schema_property
          if (schemaField.original_type) {
            const fieldType = this.app.$registry.get(
              'field',
              schemaField.original_type
            )
            suffix = `${suffix} (${fieldType.getName()})`
          }
        }
      }

      return suffix ? `${this.name} - ${suffix}` : this.name
    }

    /**
     * When a data source is modified or destroyed, we need to ensure that
     * our collection elements respond accordingly.
     *
     * If the data source has been removed, we want to remove it from the
     * collection element, and then clear its contents from the store.
     *
     * If the data source has been updated, we want to trigger a content reset.
     *
     * @param event - `ELEMENT_EVENTS.DATA_SOURCE_REMOVED` if a data source
     *  has been destroyed, or `ELEMENT_EVENTS.DATA_SOURCE_AFTER_UPDATE` if
     *  it's been updated.
     * @param params - Context data which the element type can use.
     */
    async onElementEvent(event, { builder, element, dataSourceId }) {
      const page = this.app.store.getters['page/getById'](
        builder,
        element.page_id
      )
      if (event === ELEMENT_EVENTS.DATA_SOURCE_REMOVED) {
        if (element.data_source_id === dataSourceId) {
          // Remove the data_source_id
          await this.app.store.dispatch('element/forceUpdate', {
            page,
            element,
            values: { data_source_id: null },
          })
          // Empty the element content
          await this.app.store.dispatch('elementContent/clearElementContent', {
            element,
          })
        }
      }
      if (event === ELEMENT_EVENTS.DATA_SOURCE_AFTER_UPDATE) {
        if (element.data_source_id === dataSourceId) {
          await this.app.store.dispatch(
            'elementContent/triggerElementContentReset',
            {
              element,
            }
          )
        }
      }
    }

    /**
     * A collection element is in error if:
     *
     * - No parent (including self) collection elements have a valid data_source_id.
     * - The parent with the valid data_source_id points to a data_source
     *   that !returnsList and `schema_property` is blank.
     * - It is nested in another collection element, and we don't have a `schema_property`.
     * @param {Object} page - The page the repeat element belongs to.
     * @param {Object} element - The repeat element
     * @param {Object} builder - The builder
     * @returns {Boolean} - Whether the element is in error.
     */
    isInError({ page, element, builder }) {
      // We get all parents with a valid data_source_id
      const collectionAncestorsWithDataSource = this.app.store.getters[
        'element/getAncestors'
      ](page, element, {
        predicate: (ancestor) =>
          this.app.$registry.get('element', ancestor.type)
            .isCollectionElement && ancestor.data_source_id,
        includeSelf: true,
      })

      // No parent with a data_source_id means we are in error
      if (collectionAncestorsWithDataSource.length === 0) {
        return true
      }

      // We consider the closest parent collection element with a data_source_id
      // The closest parent might be the current element itself
      const parentWithDataSource = collectionAncestorsWithDataSource.at(-1)

      // We now check if the parent element configuration is correct.
      const sharedPage = this.app.store.getters['page/getSharedPage'](builder)
      const dataSource = this.app.store.getters[
        'dataSource/getPagesDataSourceById'
      ]([page, sharedPage], parentWithDataSource.data_source_id)

      // The data source is missing. May be it has been removed.
      if (!dataSource) {
        return true
      }

      const serviceType = this.app.$registry.get('service', dataSource.type)

      // If the data source type doesn't return a list, we should have a schema_property
      if (!serviceType.returnsList && !parentWithDataSource.schema_property) {
        return true
      }

      // If the current element is not the one with the data source it should have
      // a schema_property
      if (parentWithDataSource.id !== element.id && !element.schema_property) {
        return true
      }

      return super.isInError({ page, element, builder })
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

  /**
   * Return an array of placements that are disallowed for the elements to move
   * in their container.
   *
   * @param {Object} page The page that is the parent component.
   * @param {Number} element The child element for which the placements should
   *    be calculated.
   * @returns {Array} An array of placements that are disallowed for the element.
   */
  getPlacementsDisabledForChild(page, containerElement, element) {
    return [
      PLACEMENTS.LEFT,
      PLACEMENTS.RIGHT,
      ...this.getVerticalPlacementsDisabled(page, element),
    ]
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

  getNextHorizontalElementToSelect(page, element, placement) {
    return null
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
   * @param {*} param0
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
