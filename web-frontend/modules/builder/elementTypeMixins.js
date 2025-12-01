import { ELEMENT_EVENTS, SHARE_TYPES } from '@baserow/modules/builder/enums'

export const ContainerElementTypeMixin = (Base) =>
  class extends Base {
    isContainerElement = true

    get elementTypesAll() {
      return Object.values(this.app.$registry.getAll('element'))
    }

    /**
     * Returns an array of style types that are not allowed as children of this element.
     * @returns {Array}
     */
    get childStylesForbidden() {
      return ['style_width']
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
     * A Container element without any child elements is invalid. Return true
     * if there are no children, otherwise return false.
     */
    getErrorMessage(element, applicationContext) {
      const { builder } = applicationContext

      const elementPage = this.app.store.getters['page/getById'](
        builder,
        element.page_id
      )

      const children = this.app.store.getters['element/getChildren'](
        elementPage,
        element
      )

      // A container element needs at least one child.
      if (!children.length) {
        return this.app.i18n.t('elementType.errorEmptyContainer')
      }

      return super.getErrorMessage(element, applicationContext)
    }
  }

export const CollectionElementTypeMixin = (Base) =>
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
     *  property option. If the value is `true`, and the property itself is
     *  actually capable of being refined, then the property will be
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
          ([schemaProperty, propertyValues]) =>
            (propertyValues[option] &&
              this.getPropertyOptionsByProperty(element, schemaProperty)[
                option
              ]) ||
            false
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
     * `getErrorMessage` for this purpose as it is more thorough.
     * @param element - The element we want to check for a source of data.
     * @returns {Boolean} - Whether the element has a source of data.
     */
    hasSourceOfData(element) {
      return Boolean(element.data_source_id || element.schema_property)
    }

    getElementContentInStore(element) {
      return (
        this.app.store.getters['elementContent/getElementContent'](element) ||
        []
      )
    }

    getDataSourceForElement({ builder, page, element }) {
      const sharedPage = this.app.store.getters['page/getSharedPage'](builder)
      return this.app.store.getters['dataSource/getPagesDataSourceById'](
        [sharedPage, page],
        element.data_source_id
      )
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
            builder,
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
     * A collection element is in error because of data source error if:
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
    getDataSourceErrorMessage({ workspace, page, element, builder }) {
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
        return this.$t('elementType.errorParentWithDataSourceMissing')
      }

      // A manual index is preferred over `.at()` since there are a lot of
      // users on older browsers. See GitLab issue #3591.
      const lastIndex = collectionAncestorsWithDataSource.length - 1

      // We consider the closest parent collection element with a data_source_id
      // The closest parent might be the current element itself
      const parentWithDataSource = collectionAncestorsWithDataSource[lastIndex]

      // We now check if the parent element configuration is correct.
      const sharedPage = this.app.store.getters['page/getSharedPage'](builder)
      const dataSource = this.app.store.getters[
        'dataSource/getPagesDataSourceById'
      ]([page, sharedPage], parentWithDataSource.data_source_id)

      // The data source is missing. May be it has been removed.
      if (!dataSource) {
        return this.app.i18n.t('elementType.errorDataSourceMissing')
      }

      const serviceType = this.app.$registry.get('service', dataSource.type)

      // If the data source type doesn't return a list, we should have a schema_property
      if (!serviceType.returnsList && !parentWithDataSource.schema_property) {
        return this.app.i18n.t('elementType.errorSchemaPropertyMissing')
      }

      // If the current element is not the one with the data source it should have
      // a schema_property
      if (parentWithDataSource.id !== element.id && !element.schema_property) {
        return this.app.i18n.t('elementType.errorSchemaPropertyMissing')
      }
      return null
    }

    /**
     * Check data source errors.
     */
    getErrorMessage(element, applicationContext) {
      const { workspace, builder } = applicationContext

      const elementPage = this.app.store.getters['page/getById'](
        builder,
        element.page_id
      )

      const dataSourceErrorMessage = this.getDataSourceErrorMessage({
        workspace,
        page: elementPage,
        element,
        builder,
      })

      if (dataSourceErrorMessage) {
        return dataSourceErrorMessage
      }

      return super.getErrorMessage(element, applicationContext)
    }
  }

export const MultiPageElementTypeMixin = (Base) =>
  class extends Base {
    isMultiPageElement = true

    get onSharedPage() {
      return true
    }

    isVisible({ element, applicationContext }) {
      if (!super.isVisible({ element, applicationContext })) {
        return false
      }

      const { page: currentPage } = applicationContext

      switch (element.share_type) {
        case SHARE_TYPES.ALL:
          return true
        case SHARE_TYPES.ONLY:
          return element.pages.includes(currentPage.id)
        case SHARE_TYPES.EXCEPT:
          return !element.pages.includes(currentPage.id)
        default:
          return false
      }
    }
  }
