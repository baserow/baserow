import { Registerable } from '@baserow/modules/core/registry'
import BooleanField from '@baserow/modules/builder/components/elements/components/collectionField/BooleanField'
import TextField from '@baserow/modules/builder/components/elements/components/collectionField/TextField'
import LinkField from '@baserow/modules/builder/components/elements/components/collectionField/LinkField'
import ButtonField from '@baserow/modules/builder/components/elements/components/collectionField/ButtonField.vue'
import ButtonFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/ButtonFieldForm.vue'
import BooleanFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/BooleanFieldForm'
import TagsField from '@baserow/modules/builder/components/elements/components/collectionField/TagsField.vue'
import TextFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/TextFieldForm'
import TagsFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/TagsFieldForm.vue'
import LinkFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/LinkFieldForm'
import ImageField from '@baserow/modules/builder/components/elements/components/collectionField/ImageField.vue'
import ImageFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/ImageFieldForm.vue'
import RatingField from '@baserow/modules/builder/components/elements/components/collectionField/RatingField'
import RatingFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/RatingFieldForm'
import {
  ensureArray,
  ensureBoolean,
  ensureString,
  ensureInteger,
} from '@baserow/modules/core/utils/validator'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'
import { pathParametersInError } from '@baserow/modules/builder/utils/params'
import { ClickEvent } from '@baserow/modules/builder/eventTypes'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'
import { LINK_VARIANTS } from '@baserow/modules/builder/enums'

export class CollectionFieldType extends Registerable {
  get name() {
    return null
  }

  get component() {
    return null
  }

  get formComponent() {
    return null
  }

  get events() {
    return []
  }

  getProps(field, { resolveFormula, applicationContext }) {
    return {}
  }

  getOrder() {
    return 50
  }

  /**
   * Returns error message explaining why the collection field is misconfigured.
   * @param {object} param An object containing the collection field and the builder
   * @returns The error message if the field is misconfigured, null otherwise.
   */
  getErrorMessage({ field, element, builder }) {
    return null
  }

  /**
   * Returns whether the collection field configuration is valid or not.
   * @param {object} param An object containing the collection field and the builder
   * @returns true if the collection field is in error
   */
  isInError(params) {
    return Boolean(this.getErrorMessage(params))
  }

  getStyleOverride({ colorVariables, field, theme }) {
    return ThemeConfigBlockType.getAllStyles(
      this.app.$registry.getOrderedList('themeConfigBlock'),
      field.styles?.cell || {},
      colorVariables,
      theme
    )
  }
}

export class BooleanCollectionFieldType extends CollectionFieldType {
  static getType() {
    return 'boolean'
  }

  get name() {
    return this.app.i18n.t('collectionFieldType.boolean')
  }

  get component() {
    return BooleanField
  }

  get formComponent() {
    return BooleanFieldForm
  }

  getProps(field, { resolveFormula, applicationContext }) {
    try {
      return { value: ensureBoolean(resolveFormula(field.value)) }
    } catch (error) {
      return { value: false }
    }
  }

  getErrorMessage({ field, element, builder }) {
    if (!field.value) {
      return this.app.i18n.t('collectionFieldType.errorValueMissing')
    }
    return super.getErrorMessage({ field, element, builder })
  }

  getOrder() {
    return 5
  }
}

export class TextCollectionFieldType extends CollectionFieldType {
  static getType() {
    return 'text'
  }

  get name() {
    return this.app.i18n.t('collectionFieldType.text')
  }

  get component() {
    return TextField
  }

  get formComponent() {
    return TextFieldForm
  }

  getErrorMessage({ field, element, builder }) {
    if (!field.value) {
      return this.app.i18n.t('elementType.errorValueMissing')
    }
    return super.getErrorMessage({ field, element, builder })
  }

  getProps(field, { resolveFormula, applicationContext }) {
    return { value: ensureString(resolveFormula(field.value)) }
  }

  getOrder() {
    return 10
  }
}

export class LinkCollectionFieldType extends CollectionFieldType {
  static getType() {
    return 'link'
  }

  get name() {
    return this.app.i18n.t('collectionFieldType.link')
  }

  get component() {
    return LinkField
  }

  get formComponent() {
    return LinkFieldForm
  }

  getProps(field, { resolveFormula, applicationContext: { mode, builder } }) {
    const defaultProps = {
      url: '',
      navigationType: field.navigation_type || '',
      linkName: field.link_name
        ? ensureString(resolveFormula(field.link_name))
        : null,
      target: field.target || 'self',
      variant: field.variant || LINK_VARIANTS.LINK,
    }
    try {
      return {
        ...defaultProps,
        url: resolveElementUrl(
          field,
          builder,
          this.app.store.getters['page/getVisiblePages'](builder),
          resolveFormula,
          mode
        ),
      }
    } catch (error) {
      return defaultProps
    }
  }

  getOrder() {
    return 20
  }

  /**
   * Returns whether the link field configuration has parameters in error or not.
   * @param {object} param An object containing the link field and the builder
   * @returns true if the link field is in error
   */
  getErrorMessage({ field, element, builder }) {
    if (field.navigation_type === 'page') {
      if (!field.navigate_to_page_id) {
        return this.app.i18n.t('elementType.errorNavigateToPageMissing')
      }
      if (
        pathParametersInError(
          field,
          this.app.store.getters['page/getVisiblePages'](builder)
        )
      ) {
        return this.app.i18n.t('elementType.errorPageParameterInError')
      }
    } else if (field.navigation_type === 'custom' && !field.navigate_to_url) {
      return this.app.i18n.t('elementType.errorNavigationUrlMissing')
    }

    return super.getErrorMessage({ field, element, builder })
  }
}

export class TagsCollectionFieldType extends CollectionFieldType {
  static getType() {
    return 'tags'
  }

  get name() {
    return this.app.i18n.t('collectionFieldType.tags')
  }

  get component() {
    return TagsField
  }

  get formComponent() {
    return TagsFieldForm
  }

  getErrorMessage({ field, element, builder }) {
    if (!field.values) {
      return this.app.i18n.t('elementType.errorValueMissing')
    }
    return super.getErrorMessage({ field, element, builder })
  }

  getProps(field, { resolveFormula, applicationContext }) {
    const values = ensureArray(resolveFormula(field.values))

    const colors = ensureArray(resolveFormula(field.colors))

    const tags = values.map((value, index) => ({
      value,
      color: colors[index % colors.length],
    }))
    return { tags }
  }

  getOrder() {
    return 10
  }
}

export class ButtonCollectionFieldType extends CollectionFieldType {
  static getType() {
    return 'button'
  }

  get name() {
    return this.app.i18n.t('collectionFieldType.button')
  }

  get component() {
    return ButtonField
  }

  get formComponent() {
    return ButtonFieldForm
  }

  get events() {
    return [ClickEvent]
  }

  getProps(field, { resolveFormula, applicationContext }) {
    return { label: ensureString(resolveFormula(field.label)) }
  }
}

export class ImageCollectionFieldType extends CollectionFieldType {
  static getType() {
    return 'image'
  }

  get name() {
    return this.app.i18n.t('collectionFieldType.image')
  }

  get component() {
    return ImageField
  }

  get formComponent() {
    return ImageFieldForm
  }

  getErrorMessage({ field, element, builder }) {
    if (!field.src) {
      return this.app.i18n.t('elementType.errorImageUrlMissing')
    }
    return super.getErrorMessage({ field, element, builder })
  }

  getProps(field, { resolveFormula, applicationContext }) {
    const srcs = ensureArray(resolveFormula(field.src))
    const alts = ensureArray(resolveFormula(field.alt))
    const images = srcs.map((src, index) => ({
      src,
      alt: alts[index % alts.length],
    }))
    return { images }
  }
}

export class RatingCollectionFieldType extends CollectionFieldType {
  getType() {
    return 'rating'
  }

  get name() {
    return this.app.i18n.t('collectionFieldType.rating')
  }

  get component() {
    return RatingField
  }

  get formComponent() {
    return RatingFieldForm
  }

  getErrorMessage({ field, element, builder }) {
    if (!field.value) {
      return this.app.i18n.t('collectionFieldType.errorValueMissing')
    }
    return super.getErrorMessage({ field, element, builder })
  }

  getProps(field, { resolveFormula, applicationContext }) {
    let value
    try {
      value = ensureInteger(resolveFormula(field.value), { allowNull: true })
    } catch {
      value = 0
    }

    return {
      maxValue: field.max_value || 5,
      color: field.color || 'primary',
      ratingStyle: field.rating_style || 'star',
      value,
    }
  }
}
