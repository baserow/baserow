import BigNumber from 'bignumber.js'
import {
  DURATION_FORMATS,
  formatDurationValue,
  MAX_BACKEND_DURATION_VALUE_NUMBER_OF_SECS,
  MIN_BACKEND_DURATION_VALUE_NUMBER_OF_SECS,
  parseDurationValue,
  roundDurationValueToFormat,
} from '@baserow/modules/database/utils/duration'
import {
  collatedStringCompare,
  getFilenameFromUrl,
  isInteger,
  isSimplePhoneNumber,
  isValidEmail,
  isValidURL,
} from '@baserow/modules/core/utils/string'
import { formulaFieldArrayFilterMixin } from '@baserow/modules/database/arrayFilterMixins'
import {
  parseNumberValue,
  formatNumberValue,
  formatDecimalNumber,
} from '@baserow/modules/database/utils/number'

import moment from '@baserow/modules/core/moment'
import guessFormat from 'moment-guess'
import { Registerable } from '@baserow/modules/core/registry'
import { mix } from '@baserow/modules/core/mixins'
import FieldNumberSubForm from '@baserow/modules/database/components/field/FieldNumberSubForm'
import FieldAutonumberSubForm from '@baserow/modules/database/components/field/FieldAutonumberSubForm'
import FieldDurationSubForm from '@baserow/modules/database/components/field/FieldDurationSubForm'
import FieldRatingSubForm from '@baserow/modules/database/components/field/FieldRatingSubForm'
import FieldTextSubForm from '@baserow/modules/database/components/field/FieldTextSubForm'
import FieldLongTextSubForm from '@baserow/modules/database/components/field/FieldLongTextSubForm'
import FieldDateSubForm from '@baserow/modules/database/components/field/FieldDateSubForm'
import FieldLinkRowSubForm from '@baserow/modules/database/components/field/FieldLinkRowSubForm'
import FieldMultipleSelectOptionsSubForm from '@baserow/modules/database/components/field/FieldMultipleSelectOptionsSubForm'
import FieldSingleSelectOptionsSubForm from '@baserow/modules/database/components/field/FieldSingleSelectOptionsSubForm'
import FieldCollaboratorSubForm from '@baserow/modules/database/components/field/FieldCollaboratorSubForm'
import FieldPasswordSubForm from '@baserow/modules/database/components/field/FieldPasswordSubForm'
import FieldBooleanSubForm from '@baserow/modules/database/components/field/FieldBooleanSubForm'

import GridViewFieldText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldText'
import GridViewFieldLongText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldLongText'
import GridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldRichText'
import GridViewFieldURL from '@baserow/modules/database/components/view/grid/fields/GridViewFieldURL'
import GridViewFieldEmail from '@baserow/modules/database/components/view/grid/fields/GridViewFieldEmail'
import GridViewFieldLinkRow from '@baserow/modules/database/components/view/grid/fields/GridViewFieldLinkRow'
import GridViewFieldNumber from '@baserow/modules/database/components/view/grid/fields/GridViewFieldNumber'
import GridViewFieldRating from '@baserow/modules/database/components/view/grid/fields/GridViewFieldRating'
import GridViewFieldBoolean from '@baserow/modules/database/components/view/grid/fields/GridViewFieldBoolean'
import GridViewFieldDate from '@baserow/modules/database/components/view/grid/fields/GridViewFieldDate'
import GridViewFieldDateReadOnly from '@baserow/modules/database/components/view/grid/fields/GridViewFieldDateReadOnly'
import GridViewFieldFile from '@baserow/modules/database/components/view/grid/fields/GridViewFieldFile'
import GridViewFieldSingleSelect from '@baserow/modules/database/components/view/grid/fields/GridViewFieldSingleSelect'
import GridViewFieldMultipleSelect from '@baserow/modules/database/components/view/grid/fields/GridViewFieldMultipleSelect'
import GridViewFieldPhoneNumber from '@baserow/modules/database/components/view/grid/fields/GridViewFieldPhoneNumber'
import GridViewFieldDuration from '@baserow/modules/database/components/view/grid/fields/GridViewFieldDuration'
import GridViewFieldMultipleCollaborators from '@baserow/modules/database/components/view/grid/fields/GridViewFieldMultipleCollaborators'
import GridViewFieldUUID from '@baserow/modules/database/components/view/grid/fields/GridViewFieldUUID'
import GridViewFieldAutonumber from '@baserow/modules/database/components/view/grid/fields/GridViewFieldAutonumber'
import GridViewFieldLastModifiedBy from '@baserow/modules/database/components/view/grid/fields/GridViewFieldLastModifiedBy'
import GridViewFieldPassword from '@baserow/modules/database/components/view/grid/fields/GridViewFieldPassword'

import FunctionalGridViewFieldText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldText'
import FunctionalGridViewFieldDuration from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldDuration'
import FunctionalGridViewFieldLongText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldLongText'
import FunctionalGridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldRichText'
import FunctionalGridViewFieldLinkRow from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldLinkRow'
import FunctionalGridViewFieldNumber from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldNumber'
import FunctionalGridViewFieldRating from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldRating'
import FunctionalGridViewFieldBoolean from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldBoolean'
import FunctionalGridViewFieldDate from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldDate'
import FunctionalGridViewFieldFile from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldFile'
import FunctionalGridViewFieldSingleSelect from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldSingleSelect'
import FunctionalGridViewFieldMultipleSelect from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldMultipleSelect'
import FunctionalGridViewFieldFormula from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldFormula'
import FunctionalGridViewFieldMultipleCollaborators from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldMultipleCollaborators'
import FunctionalGridViewFieldURL from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldURL'
import FunctionalGridViewFieldUUID from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldUUID'
import FunctionalGridViewFieldAutonumber from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldAutonumber'
import FunctionalGridViewFieldLastModifiedBy from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldLastModifiedBy'
import FunctionalGridVIewFieldPassword from '@baserow/modules/database/components/view/grid/fields/FunctionalGridVIewFieldPassword.vue'

import RowEditFieldText from '@baserow/modules/database/components/row/RowEditFieldText'
import RowEditFieldLongText from '@baserow/modules/database/components/row/RowEditFieldLongText'
import RowEditFieldRichText from '@baserow/modules/database/components/row/RowEditFieldRichText'
import RowEditFieldURL from '@baserow/modules/database/components/row/RowEditFieldURL'
import RowEditFieldEmail from '@baserow/modules/database/components/row/RowEditFieldEmail'
import RowEditFieldLinkRow from '@baserow/modules/database/components/row/RowEditFieldLinkRow'
import RowEditFieldNumber from '@baserow/modules/database/components/row/RowEditFieldNumber'
import RowEditFieldDuration from '@baserow/modules/database/components/row/RowEditFieldDuration'
import RowEditFieldRating from '@baserow/modules/database/components/row/RowEditFieldRating'
import RowEditFieldBoolean from '@baserow/modules/database/components/row/RowEditFieldBoolean'
import RowEditFieldDate from '@baserow/modules/database/components/row/RowEditFieldDate'
import RowEditFieldDateReadOnly from '@baserow/modules/database/components/row/RowEditFieldDateReadOnly'
import RowEditFieldFile from '@baserow/modules/database/components/row/RowEditFieldFile'
import RowEditFieldSingleSelect from '@baserow/modules/database/components/row/RowEditFieldSingleSelect'
import RowEditFieldMultipleSelect from '@baserow/modules/database/components/row/RowEditFieldMultipleSelect'
import RowEditFieldPhoneNumber from '@baserow/modules/database/components/row/RowEditFieldPhoneNumber'
import RowEditFieldMultipleCollaborators from '@baserow/modules/database/components/row/RowEditFieldMultipleCollaborators'
import RowEditFieldUUID from '@baserow/modules/database/components/row/RowEditFieldUUID'
import RowEditFieldAutonumber from '@baserow/modules/database/components/row/RowEditFieldAutonumber'
import RowEditFieldLastModifiedBy from '@baserow/modules/database/components/row/RowEditFieldLastModifiedBy'
import RowEditFieldPassword from '@baserow/modules/database/components/row/RowEditFieldPassword'

import RowCardFieldBoolean from '@baserow/modules/database/components/card/RowCardFieldBoolean'
import RowCardFieldDate from '@baserow/modules/database/components/card/RowCardFieldDate'
import RowCardFieldDuration from '@baserow/modules/database/components/card/RowCardFieldDuration'
import RowCardFieldEmail from '@baserow/modules/database/components/card/RowCardFieldEmail'
import RowCardFieldFile from '@baserow/modules/database/components/card/RowCardFieldFile'
import RowCardFieldFormula from '@baserow/modules/database/components/card/RowCardFieldFormula'
import RowCardFieldLinkRow from '@baserow/modules/database/components/card/RowCardFieldLinkRow'
import RowCardFieldMultipleSelect from '@baserow/modules/database/components/card/RowCardFieldMultipleSelect'
import RowCardFieldNumber from '@baserow/modules/database/components/card/RowCardFieldNumber'
import RowCardFieldRating from '@baserow/modules/database/components/card/RowCardFieldRating'
import RowCardFieldPhoneNumber from '@baserow/modules/database/components/card/RowCardFieldPhoneNumber'
import RowCardFieldSingleSelect from '@baserow/modules/database/components/card/RowCardFieldSingleSelect'
import RowCardFieldText from '@baserow/modules/database/components/card/RowCardFieldText'
import RowCardFieldRichText from '@baserow/modules/database/components/card/RowCardFieldRichText'
import RowCardFieldURL from '@baserow/modules/database/components/card/RowCardFieldURL'
import RowCardFieldMultipleCollaborators from '@baserow/modules/database/components/card/RowCardFieldMultipleCollaborators'
import RowCardFieldUUID from '@baserow/modules/database/components/card/RowCardFieldUUID'
import RowCardFieldAutonumber from '@baserow/modules/database/components/card/RowCardFieldAutonumber'
import RowCardFieldLastModifiedBy from '@baserow/modules/database/components/card/RowCardFieldLastModifiedBy'
import RowCardFieldPassword from '@baserow/modules/database/components/card/RowCardFieldPassword'

import RowHistoryFieldText from '@baserow/modules/database/components/row/RowHistoryFieldText'
import RowHistoryFieldRichText from '@baserow/modules/database/components/row/RowHistoryFieldRichText'
import RowHistoryFieldDate from '@baserow/modules/database/components/row/RowHistoryFieldDate'
import RowHistoryFieldNumber from '@baserow/modules/database/components/row/RowHistoryFieldNumber'
import RowHistoryFieldDuration from '@baserow/modules/database/components/row/RowHistoryFieldDuration'
import RowHistoryFieldMultipleCollaborators from '@baserow/modules/database/components/row/RowHistoryFieldMultipleCollaborators'
import RowHistoryFieldFile from '@baserow/modules/database/components/row/RowHistoryFieldFile'
import RowHistoryFieldMultipleSelect from '@baserow/modules/database/components/row/RowHistoryFieldMultipleSelect'
import RowHistoryFieldSingleSelect from '@baserow/modules/database/components/row/RowHistoryFieldSingleSelect'
import RowHistoryFieldBoolean from '@baserow/modules/database/components/row/RowHistoryFieldBoolean'
import RowHistoryFieldLinkRow from '@baserow/modules/database/components/row/RowHistoryFieldLinkRow'
import RowHistoryFieldPassword from '@baserow/modules/database/components/row/RowHistoryFieldPassword'

import FormViewFieldLinkRow from '@baserow/modules/database/components/view/form/FormViewFieldLinkRow'
import FormViewFieldMultipleLinkRow from '@baserow/modules/database/components/view/form/FormViewFieldMultipleLinkRow'
import FormViewFieldMultipleSelectCheckboxes from '@baserow/modules/database/components/view/form/FormViewFieldMultipleSelectCheckboxes'
import FormViewFieldMultipleCollaboratorsCheckboxes from '@baserow/modules/database/components/view/form/FormViewFieldMultipleCollaboratorsCheckboxes'
import FormViewFieldSingleSelectRadios from '@baserow/modules/database/components/view/form/FormViewFieldSingleSelectRadios'

import {
  getDateMomentFormat,
  getFieldTimezone,
  getTimeMomentFormat,
} from '@baserow/modules/database/utils/date'
import {
  filenameContainsFilter,
  genericContainsFilter,
  genericContainsWordFilter,
  genericHasValueEqualFilter,
} from '@baserow/modules/database/utils/fieldFilters'
import GridViewFieldFormula from '@baserow/modules/database/components/view/grid/fields/GridViewFieldFormula'
import FieldFormulaSubForm from '@baserow/modules/database/components/field/FieldFormulaSubForm'
import FieldLookupSubForm from '@baserow/modules/database/components/field/FieldLookupSubForm'
import FieldCountSubForm from '@baserow/modules/database/components/field/FieldCountSubForm'
import FieldRollupSubForm from '@baserow/modules/database/components/field/FieldRollupSubForm'
import RowEditFieldFormula from '@baserow/modules/database/components/row/RowEditFieldFormula'
import {
  DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY,
  DEFAULT_SORT_TYPE_KEY,
  LINKED_ITEMS_DEFAULT_LOAD_COUNT,
} from '@baserow/modules/database/constants'
import ViewService from '@baserow/modules/database/services/view'
import FormService from '@baserow/modules/database/services/view/form'
import { UploadFileUserFileUploadType } from '@baserow/modules/core/userFileUploadTypes'
import _, { clone } from 'lodash'
import { trueValues } from '@baserow/modules/core/utils/constants'
import ViewFilterTypeNumber from '@baserow/modules/database/components/view/ViewFilterTypeNumber.vue'
import ViewFilterTypeDuration from '@baserow/modules/database/components/view/ViewFilterTypeDuration.vue'
import FormViewFieldOptionsAllowedSelectOptions from '@baserow/modules/database/components/view/form/FormViewFieldOptionsAllowedSelectOptions'

export class FieldType extends Registerable {
  /**
   * The icon class name that is used as convenience for the user to
   * recognize certain field types. If you for example want the database
   * icon, you must return 'database' here. This will result in the classname
   * 'iconoir-database'.
   */
  static getIconClass() {
    return null
  }

  getIconClass() {
    return this.constructor.getIconClass()
  }

  /**
   * A human readable name of the view type.
   */
  getName() {
    return null
  }

  /**
   * The form component will be added to the field type context component if the
   * matching type is selected. This component is used to create and update
   * fields and should contain the unique inputs needed for this type. For
   * example if we are creating a number fields this component should contain
   * the inputs to choose of it is an integer of decimal.
   */
  getFormComponent(field) {
    return null
  }

  /**
   * This grid view field component should represent the related row value of this
   * type. It will only be used in the grid view and it also responsible for editing
   * the value.
   */
  getGridViewFieldComponent(field) {
    throw new Error(
      'Not implement error. This method should return a component.'
    )
  }

  /**
   * This method generates the context menu options for actions that can be performed on
   * more selected cells within the same field. These options appear in the grid view
   * when the user right-clicks on multiple cells.
   * @param field The field object.
   */
  getGridViewContextItemsOnCellsSelection(field) {
    return []
  }

  /**
   * This functional component should represent an unselect field cell related to the
   * value of this type. It will only be used in the grid view and is only for fast
   * displaying purposes, not for editing the value. This is because functional
   * components are much faster. When a user clicks on the cell it will be replaced
   * with the real component.
   */
  getFunctionalGridViewFieldComponent(field) {
    throw new Error(
      'Not implement error. This method should return a component.'
    )
  }

  /**
   * The row edit field should represent a the related row value of this type. It
   * will be used in the row edit modal, but can also be used in other forms. It is
   * responsible for editing the value.
   */
  getRowEditFieldComponent(field) {
    throw new Error(
      'Not implement error. This method should return a component.'
    )
  }

  /**
   * By default, the edit field component is used in the form. This can optionally be
   * replaced by another component if needed. If an empty object `{}` is returned,
   * then the field is marked as not compatible with the form view.
   *
   * The returned object should have one key with an empty string `''` as default
   * component. If the object has multiple keys, then the user will be presented
   * with these as options. This can be used to for example display a `single_select`
   * field type as dropdown or radio inputs.
   */
  getFormViewFieldComponents(field) {
    const { i18n } = this.app
    return {
      [DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY]: {
        name: i18n.t('fieldType.defaultFormViewComponent'),
        component: this.getRowEditFieldComponent(field),
        properties: {},
      },
    }
  }

  /**
   * This hook is called in the form view editing mode. It allows to change the
   * field values per field type. These field values are only passed into the input
   * component. The form view component is sometimes the same as the row edit modal
   * field component, so unique changes can't always be made there. Hence this hook
   * to prepare the values.
   */
  prepareFormViewFieldForFormEditInput(field) {
    return field
  }

  /**
   * Can optionally return a component that's rendered inside the form view, and can
   * be used to configure field specific field options.
   */
  getFormViewFieldOptionsComponent(field) {
    return null
  }

  /**
   * This component should represent the field's value in a row card display. To
   * improve performance, this component should be a functional component.
   */
  getCardComponent(field) {
    throw new Error(
      'Not implement error. This method should return a component.'
    )
  }

  /**
   * This component should represent the grouped by field's value in the grid view. To
   * improve performance, this component should be a functional component. The card
   * component almost always compatible here, so we're returning that one by default.
   */
  getGroupByComponent(field) {
    return this.getCardComponent(field)
  }

  /**
   * This component displays row change difference for values of the field type.
   */
  getRowHistoryEntryComponent() {
    return null
  }

  getCompatibleFilterFieldType(field) {
    return this
  }

  /**
   * In some cases, for example with the kanban view or the gallery view, we want to
   * only show the visible cards. In order to calculate the correct position of
   * those cards, we need to know the height. Because every field could have a
   * different height in the card, it must be returned here.
   */
  getCardValueHeight(field) {
    return this.getCardComponent(field).height || 0
  }

  /**
   * Should return the empty value for the field type.
   */
  getEmptyValue(field) {
    return null
  }

  /**
   * Because we want to show a new row immediately after creating we need to have an
   * default value to show right away.
   *
   * @param field - The field object.
   * @param flat - If true, returns a simplified default value suitable for
   *  backend operations (such as IDs or primitives). If false, returns the
   *  full object representation, which may include additional metadata for
   *  frontend use. This allows flexibility depending on whether a minimal or
   *  detailed value is required.
   */
  getDefaultValue(field, flat) {
    return null
  }

  /**
   * Returns the name of the field that contains the default value.
   */
  getDefaultValueFieldName() {
    return null
  }

  /**
   * Should return true if the provided value is empty.
   */
  isEmpty(field, value) {
    const isEmptyValue = (v) => {
      return (
        [null, undefined].includes(v) ||
        String(v).trim() === '' ||
        (Array.isArray(v) && v.length === 0)
      )
    }
    if (
      Array.isArray(value) &&
      (value.length === 0 ||
        value.every((i) => isEmptyValue(i.value ?? i.name)))
    ) {
      return true
    }
    if (
      value !== null &&
      typeof value === 'object' &&
      Object.keys(value).length === 0
    ) {
      return true
    }
    return value === false || isEmptyValue(value)
  }

  /**
   * Should return true if both provided row values are equal. This is used to determine
   * whether they both belong in the same group for example. It's not possible to
   * compare a group value and row value, in that case the
   * `getRowValueFromGroupValue` method be called first to convert to a row value.
   */
  isEqual(field, value1, value2) {
    return JSON.stringify(value1) === JSON.stringify(value2)
  }

  /**
   * Should return a string containing the error if the value is invalid. If the
   * value is valid, then null must be returned.
   */
  getValidationError(field, value) {
    return null
  }

  /**
   * Indicates whether or not it is possible to sort in a view.
   */
  getCanSortInView(field) {
    return true
  }

  /**
   * Indicates whether or not it is possible to group by this field in a view.
   */
  getCanGroupByInView(field) {
    return false
  }

  /**
   * In some cases, the group by value can not be directly compared to a row value
   * because the format is different for technical reasons in the backend. This
   * method can be used to convert it to a row value that can be used in combination
   * with the `isEqual` method.
   *
   * An example is with a ManyToMany field, where the backend group by value is
   * `{id},{id2}` as a string, but in the frontend, this should be an array like
   * `[1, 2]`.
   */
  getRowValueFromGroupValue(field, value) {
    return value
  }

  /**
   * In some cases, the new group entry must be created that doesn't yet exist. In
   * that scenario, we do have the row value. This method should convert the row
   * value to a group value so that it can be used there.
   *
   * An example is with a ManyToMany field, where the frontend value is an object
   * containing ids, but the group by value is a string containing the ids joined by
   * a comma.
   */
  getGroupValueFromRowValue(field, value) {
    return value
  }

  /**
   * Indicates if is possible for the field type to be the primary field.
   */
  getCanBePrimaryField() {
    return true
  }

  /**
   * When true, indicates a field type that can be used to
   * represent a date.
   */
  canRepresentDate(field) {
    return false
  }

  /**
   * When true, indicates a field type can be used
   * to supply a list of files.
   */
  canRepresentFiles(field) {
    return false
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()
    this.canBePrimaryField = this.getCanBePrimaryField()

    if (this.type === null) {
      throw new Error('The type name of a view type must be set.')
    }
    if (this.iconClass === null) {
      throw new Error('The icon class of a view type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of a view type must be set.')
    }
  }

  /**
   * Every time a fresh field object is fetched from the backend, it will be
   * populated, this is the moment to update some values. Because each view type
   * can have unique properties, they might need to be populated. This method
   * can be overwritten in order the populate the correct values.
   */
  populate(field) {
    return field
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      name: this.getName(),
      canImport: this.getCanImport(),
      canBePrimaryField: this.canBePrimaryField,
    }
  }

  /**
   * Should return a for humans readable representation of the value. This is for
   * example used by the link row field and row modal. This is not a problem with most
   * fields like text or number, but some store a more complex object like
   * the single select or file field. In this case, the object might needs to be
   * converted to string.
   */
  toHumanReadableString(field, value, delimiter = ', ') {
    return value || ''
  }

  /**
   * Return a representation of the value in the aggregation context.
   */
  toAggregationString(field, value) {
    return this.toHumanReadableString(field, value)
  }

  /**
   * When searching a cells value this should return the value to match the users
   * user term against.
   */
  toSearchableString(field, value, delimiter = ', ') {
    return this.toHumanReadableString(field, value, delimiter)
  }

  /**
   * Should return a sort function that is unique for the field type.
   */
  getSort() {
    throw new Error(
      'Not implement error. This method should by a sort function.'
    )
  }

  /**
   * Should return a visualisation of how the sort function is going to work. For
   * example ['text', 'A', 'Z'] will result in 'A -> Z' as ascending and 'Z -> A'
   * descending visualisation for the user. It is also possible to use a icon class name
   * icon here by changing the first value to 'icon'. For example
   * ['icon', 'square', 'security-pass'].
   */
  getSortIndicator() {
    return ['text', 'A', 'Z']
  }

  /**
   * Should return a mapping containing all the available sort types for this field
   * type. It always returns the default type, which uses the `getSort` and
   * `getSortIndicator` by default.
   */
  getSortTypes(field) {
    return {
      [DEFAULT_SORT_TYPE_KEY]: {
        function: this.getSort.bind(this),
        indicator: this.getSortIndicator(field),
      },
    }
  }

  /**
   * Can a field of this type be used to perform an update during import on rows that
   * contain the same value as imported one.
   */
  canUpsert() {
    return false
  }

  /**
   * This hook is called before the field's value is copied to the clipboard.
   * Optionally formatting can be done here. By default the value is always
   * converted to a string.
   */
  prepareValueForCopy(field, value) {
    // In case that the 'value' is null or undefined (which means that the cell is empty)
    // we simply want to return an empty string.
    if (value == null) {
      return ''
    } else {
      return value.toString()
    }
  }

  /**
   * Some fields need two representations: a simple textual one returned by
   * `.prepareValueForCopy()` but also a rich representation in json to avoid data
   * loss while copying. For example: a select field can have multiple options with the
   * same name. If we copy just text, we'll loose which option it was before if there
   * are duplicate name but with the rich version we can restore the exact same data.
   * The value returned by this method is then copied in a specific clipboard buffer to
   * avoid messing up with the text buffer. The returned value must be json
   * serializable.
   * This method don't have to be redefined and return `prepareValueForCopy()` value
   * by default.
   */
  prepareRichValueForCopy(field, value) {
    return this.prepareValueForCopy(field, value)
  }

  /**
   * This hook is called before the field's value is overwritten by the clipboard
   * data. That data might needs to be prepared so that the field accepts it.
   * By default the input value is returned as is. You can also use the
   * `richClipboardData` parameter to restore a field without data loss. Using this
   * parameter only makes sense if you've also defined a specific
   * `.prepareRichValueForCopy()` method that return this rich value.
   */
  prepareValueForPaste(field, clipboardData, richClipboardData) {
    return clipboardData
  }

  /**
   * This hook is called just before a row is duplicated, and the create request is
   * made. It allows to modify the value if needed.
   */
  prepareValueForDuplicate(field, value) {
    return value
  }

  /**
   * Optionally the value can be prepared just before the update API call is being
   * made. The new value is not going to saved in the store it is just for preparing
   * the value such that it fits the requirements of the API endpoint.
   */
  prepareValueForUpdate(field, value) {
    return value
  }

  /**
   * A hook that is called when a table is deleted. Some fields depend on other tables
   * than the table that they belong to. So action might be required when that table
   * is deleted.
   */
  tableDeleted(context, field, table, database) {}

  /**
   * Should return a string indicating which data type is expected. (e.g. string). The
   * value is shown in the documentation above the description.
   */
  getDocsDataType(field) {
    throw new Error('The docs data type must be set.')
  }

  /**
   * Should return a single line description explaining which value is expected for
   * the field. The value is shown in the overview of fields.
   */
  getDocsDescription(field) {
    throw new Error('The docs description must be set.')
  }

  /**
   * Should return an example value of the data. Will be shown in the request and
   * response examples.
   */
  getDocsRequestExample(field) {
    throw new Error('The docs example must be set.')
  }

  /**
   * If the response value differs from the accepted value as request then an
   * alternative can be provided here. By default the request example is returned
   * here.
   */
  getDocsResponseExample(field) {
    return this.getDocsRequestExample(field)
  }

  /**
   * Generate a field sample for the given field that is displayed in auto-doc.
   * @returns a sample for this field.
   */
  getDocsFieldResponseExample(
    { id, table_id: tableId, name, order, type, primary, description },
    readOnly
  ) {
    return {
      id,
      table_id: tableId,
      name,
      order,
      type,
      primary,
      read_only: readOnly,
      description: description || 'A sample description',
    }
  }

  /**
   * Should return a contains filter function unique for this field type.
   */
  getContainsFilterFunction() {
    return (rowValue, humanReadableRowValue, filterValue) => false
  }

  /**
   * Should return a contains word filter function unique for this field type.
   */
  getContainsWordFilterFunction(field) {
    return (rowValue, humanReadableRowValue, filterValue) => false
  }

  /**
   * Converts rowValue to its human readable form first before applying the
   * filter returned from getContainsFilterFunction.
   */
  containsFilter(rowValue, filterValue, field) {
    return (
      filterValue === '' ||
      this.getContainsFilterFunction(field)(
        rowValue,
        this.toHumanReadableString(field, rowValue),
        filterValue
      )
    )
  }

  /**
   * Converts rowValue to its human readable form first before applying the field
   * filter returned by getContainsFilterFunction's notted.
   */
  notContainsFilter(rowValue, filterValue, field) {
    return (
      filterValue === '' ||
      !this.getContainsFilterFunction(field)(
        rowValue,
        this.toHumanReadableString(field, rowValue),
        filterValue
      )
    )
  }

  /**
   * Converts rowValue to its human readable form first before applying the
   * filter returned from getContainsWordFilterFunction.
   */
  containsWordFilter(rowValue, filterValue, field) {
    return (
      filterValue === '' ||
      this.getContainsWordFilterFunction(field)(
        rowValue,
        this.toHumanReadableString(field, rowValue),
        filterValue
      )
    )
  }

  /**
   * Converts rowValue to its human readable form first before applying the field
   * filter returned by getContainsWordFilterFunction's notted.
   */
  doesntContainWordFilter(rowValue, filterValue, field) {
    return (
      filterValue === '' ||
      !this.getContainsWordFilterFunction(field)(
        rowValue,
        this.toHumanReadableString(field, rowValue),
        filterValue
      )
    )
  }

  /**
   * Returns optionally input component for a field / filter type combination.
   * This is called by FilterType to get the component. FilterType should provide
   * a default if FieldType returns null.
   *
   * @returns {null}
   */
  getFilterInputComponent(field, filterType) {
    return null
  }

  /**
   * Return a valid filter value for the field type. This is used to parse the
   * filter value from the frontend to the backend.
   */
  parseFilterValue(field, filterValue) {
    return filterValue
  }

  /**
   * Given a field value, format it as a string to be used in a filter value
   * and sent to the backend.
   */
  formatFilterValue(field, value) {
    return String(value ?? '')
  }

  /**
   * Is called for each field in the row when another field value in the row has
   * changed. Optionally, a different value can be returned here for that field. This
   * is for example used by the last modified field type to update the last modified
   * value in real time when a row has changed.
   */
  onRowChange(row, currentField, currentFieldValue) {
    return currentFieldValue
  }

  /**
   * Is called for each field in the row when a row has moved to another position.
   * Optionally, a different value can be returned here for that field. This is for
   * example used by the last modified field type to update the last modified value
   * in real time when a row has moved.
   */
  onRowMove(row, order, oldOrder, currentField, currentFieldValue) {
    return currentFieldValue
  }

  /**
   * Is called for each field in a row when a new row is being created. This can be
   * used to set a default value. This value will be added to the row before the
   * call submitted to the backend, so the user will immediately see it.
   */
  getNewRowValue(field) {
    return this.getDefaultValue(field)
  }

  /**
   * Determines whether row data of the field should be fetched again after the
   * field has been created. This is for example needed when a value depends on the
   * backend and can't be guessed or calculated by the web-frontend.
   */
  shouldFetchDataWhenAdded() {
    return false
  }

  /**
   * Determines whether the field type is inherently read-only, such as a
   * FormulaFieldType or CreatedOnFieldType, which are always read-only. Some fields may
   * have the `read_only` attribute set, indicating that while the field type itself is
   * not inherently read-only, the specific field instance is, such as in the case of
   * data-synced fields. Read-only fields are excluded from update requests to the
   * backend and cannot have their values modified, for example, by pasting.
   */
  isReadOnlyField(field) {
    return Boolean(field.read_only)
  }

  /**
   * Determines if it is possible to write values to the field. This is used to
   * determine if the field values are editable in the UI. To be able to write
   * values, the field type must not be read-only and the user must have
   * permission to write to the field.
   */
  canWriteFieldValues(field) {
    return (
      !this.isReadOnlyField(field) &&
      this.app.$hasPermission(
        'database.table.field.write_values',
        field,
        field.workspace_id
      )
    )
  }

  /**
   * Determines if it is possible to submit anonymous values to the field. This is used
   * to determine if the field will be shown in form views.
   */
  canSubmitAnonymousValues(field) {
    return (
      !this.isReadOnlyField(field) &&
      this.app.$hasPermission(
        'database.table.field.submit_anonymous_values',
        field,
        field.workspace_id
      )
    )
  }

  /**
   * Override and return true if the field type can be referenced by a formula field.
   * @return {boolean}
   */
  canBeReferencedByFormulaField(field) {
    return false
  }

  /**
   * Determines whether a field type should automatically fetch select options
   * when switching to a field type that supports select options, like the single or
   * multiple select.
   */
  shouldFetchFieldSelectOptions() {
    return true
  }

  /**
   * Indicates whether this field type accepts single select suggestions splitted by
   * a comma.  This is for example the case with a multiple select field because
   * splits old values by comma on conversion.
   */
  acceptSplitCommaSeparatedSelectOptions() {
    return false
  }

  /**
   * Determines whether the field type value can be set by
   * parsing a query parameter.
   * @returns {boolean}
   */
  canParseQueryParameter() {
    return false
  }

  /**
   * Parse a value given by a url query parameter.
   * @param {string} value
   * @param field
   * @param options Any additional information that might be needed for the parsing
   * @returns {*}
   */
  parseQueryParameter(field, value, options) {
    return value
  }

  /**
   * Determines whether the field type value can be imported from a file
   * @returns {boolean}
   */
  getCanImport() {
    return false
  }

  /**
   * Parse a value given as input. This Can be used to convert values from
   * different formats to the format that is used by the field type. For example
   * a date field could accept a string like '2020-01-01' and convert it to a
   * moment object, or a duration field can accept a string like '1:30' to
   * convert it to a number of seconds.
   */
  parseInputValue(field, value) {
    return value
  }

  /**
   * Parse a value of for the field type from a linked row item value. This can be
   * used to convert values provided by a linked row item to the format that is used
   * by the field type to sort, filter, etc. in the frontend.
   */
  parseFromLinkedRowItemValue(field, value) {
    return value
  }

  /**
   * Indicates whether it's possible to select the field type when creating or updating the field.
   */
  isEnabled(workspace) {
    return true
  }

  /**
   * Can return a modal vue component that's opened when the user clicks in this
   * field type, but `isEnabled` is false. Should return [component, props as {}]
   */
  getDisabledClickModal(workspace) {
    return null
  }

  /**
   * Can return a tooltip text that's shown on hover when the `isEnabled` is False.
   */
  getDisabledTooltip(workspace) {
    return null
  }

  /**
   * Indicates whether the field is visible, but in a deactivated state.
   */
  isDeactivated(workspaceId) {
    return false
  }

  /**
   * The modal that must be shown when a deactivated field is clicked.
   */
  getDeactivatedClickModal(workspaceId) {
    return null
  }

  /**
   * Alternative text used when searching for the field.
   */
  getAlias() {
    return null
  }

  toBaserowFormulaType(field) {
    return this.getType()
  }

  /**
   * Checks if all required data for the given field and rows is loaded. Returns true if
   * any data is missing and needs to be refetched from the server. This is useful, for
   * example, when copying link row fields with many relations: not all related data is
   * loaded immediately for performance reasons, but full data is needed for copy/paste
   * operations.
   *
   * @param {Object} field - The field object.
   * @param {Array} rows - The rows to check.
   * @returns {boolean} - True if data needs to be refetched, false otherwise.
   */
  shouldRefetchFieldData(field, rows) {
    return false
  }

  /**
   * Indicates whether it's possible to enable the database index for a field.
   */
  canHaveDbIndex(fieldValues) {
    return false
  }
}

class SelectOptionBaseFieldType extends FieldType {
  prepareFormViewFieldForFormEditInput(field, fieldOptions) {
    const updatedField = clone(field)
    updatedField.select_options = updatedField.select_options.filter(
      (selectOption) => {
        return (
          fieldOptions.include_all_select_options ||
          fieldOptions.allowed_select_options.includes(selectOption.id)
        )
      }
    )
    return updatedField
  }

  getFormViewFieldOptionsComponent() {
    return FormViewFieldOptionsAllowedSelectOptions
  }

  formatFilterValue(field, value) {
    // Filter out any invalid option IDs before sending to the backend.
    // This prevents confusion where invalid IDs might be interpreted as no option selected,
    // but the backend will reject them.
    const validOptionIds = field.select_options.map((option) =>
      String(option.id)
    )
    return value
      .split(',')
      .filter((id) => validOptionIds.includes(String(id)))
      .join(',')
  }
}

export class TextFieldType extends FieldType {
  static getType() {
    return 'text'
  }

  static getIconClass() {
    return 'iconoir-text'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.singleLineText')
  }

  getAlias() {
    return 'string'
  }

  getFormComponent() {
    return FieldTextSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldText
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldText
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldText
  }

  getCardComponent() {
    return RowCardFieldText
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldText
  }

  getEmptyValue(field) {
    return ''
  }

  getDefaultValueFieldName() {
    return 'text_default'
  }

  getDefaultValue(field, flat) {
    const defaultValueFieldName = this.getDefaultValueFieldName()
    return field[defaultValueFieldName] || this.getEmptyValue(field)
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const stringA = a[name] === null ? '' : '' + a[name]
      const stringB = b[name] === null ? '' : '' + b[name]
      return collatedStringCompare(stringA, stringB, order)
    }
  }

  getDocsDataType(field) {
    return 'string'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.text')
  }

  getDocsRequestExample(field) {
    return 'string'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  getContainsWordFilterFunction(field) {
    return genericContainsWordFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canParseQueryParameter() {
    return true
  }

  getCanImport() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }

  canHaveDbIndex(fieldValues) {
    return true
  }
}

export class LongTextFieldType extends FieldType {
  static getType() {
    return 'long_text'
  }

  static getIconClass() {
    return 'iconoir-align-left'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.longText')
  }

  getAlias() {
    return 'multiline multi-line rich string'
  }

  getFormComponent() {
    return FieldLongTextSubForm
  }

  getGridViewFieldComponent(field) {
    if (field?.long_text_enable_rich_text) {
      return GridViewFieldRichText
    } else {
      return GridViewFieldLongText
    }
  }

  getFunctionalGridViewFieldComponent(field) {
    if (field?.long_text_enable_rich_text) {
      return FunctionalGridViewFieldRichText
    } else {
      return FunctionalGridViewFieldLongText
    }
  }

  getRowEditFieldComponent(field) {
    if (field?.long_text_enable_rich_text) {
      return RowEditFieldRichText
    } else {
      return RowEditFieldLongText
    }
  }

  getCardComponent(field) {
    if (field?.long_text_enable_rich_text) {
      return RowCardFieldRichText
    } else {
      return RowCardFieldText
    }
  }

  getRowHistoryEntryComponent(field) {
    if (field?.long_text_enable_rich_text) {
      return RowHistoryFieldRichText
    } else {
      return RowHistoryFieldText
    }
  }

  getDefaultValue(field, flat) {
    return ''
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const stringA = a[name] === null ? '' : '' + a[name]
      const stringB = b[name] === null ? '' : '' + b[name]

      return collatedStringCompare(stringA, stringB, order)
    }
  }

  getDocsDataType(field) {
    return 'string'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.longText')
  }

  getDocsRequestExample(field) {
    return 'string'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  getContainsWordFilterFunction(field) {
    return genericContainsWordFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canParseQueryParameter() {
    return true
  }

  getCanImport() {
    return true
  }

  getCanGroupByInView(field) {
    return !field.long_text_enable_rich_text
  }

  canHaveDbIndex(fieldValues) {
    return true
  }
}

export class LinkRowFieldType extends FieldType {
  static getType() {
    return 'link_row'
  }

  static getIconClass() {
    return 'iconoir-ev-plug'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.linkToTable')
  }

  getAlias() {
    return 'foreign key'
  }

  getFormComponent() {
    return FieldLinkRowSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldLinkRow
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldLinkRow
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldLinkRow
  }

  getFormViewFieldComponents(field) {
    const { i18n } = this.app
    const components = super.getFormViewFieldComponents(field)
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].name = i18n.t(
      'fieldType.linkRowSingle'
    )
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].component =
      FormViewFieldLinkRow
    // No need to offer the multiple variant if the field type is configured to only
    // select one relation.
    if (field.link_row_multiple_relationships) {
      components.multiple = {
        name: i18n.t('fieldType.linkRowMultiple'),
        component: FormViewFieldMultipleLinkRow,
        properties: {},
      }
    }
    return components
  }

  getCardComponent() {
    return RowCardFieldLinkRow
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldLinkRow
  }

  getDefaultValue(field, flat) {
    return []
  }

  getEmptyValue(field) {
    return []
  }

  getCanGroupByInView(field) {
    const relatedField = field.link_row_table_primary_field
    const relatedFieldType = this.app.$registry.get('field', relatedField.type)
    return relatedFieldType.getCanGroupByInView(relatedField)
  }

  getGroupValueFromRowValue(field, value) {
    return (value || []).map((row) => row.id)
  }

  getRowValueFromGroupValue(field, value) {
    return (value || []).map((rowId) => ({ id: rowId }))
  }

  isEqual(field, value1, value2) {
    const value1Ids = value1.map((v) => v.id)
    const value2Ids = value2.map((v) => v.id)

    return _.isEqual(value1Ids, value2Ids)
  }

  getCanSortInView(field) {
    const relatedField = field.link_row_table_primary_field
    const relatedFieldType = this.app.$registry.get('field', relatedField.type)
    return relatedFieldType.getCanSortInView(relatedField)
  }

  getSort(name, order, field) {
    const relatedPrimaryField = field.link_row_table_primary_field
    const relatedPrimaryFieldType = this.app.$registry.get(
      'field',
      relatedPrimaryField.type
    )
    const relatedSortFunc = relatedPrimaryFieldType.getSort(
      name,
      order,
      relatedPrimaryField
    )
    const relatedParseFunc = (item) => {
      return relatedPrimaryFieldType.parseFromLinkedRowItemValue(
        relatedPrimaryField,
        item?.value
      )
    }

    return (a, b) => {
      const valuesA = a[name].map(relatedParseFunc)
      const valuesB = b[name].map(relatedParseFunc)
      const lenA = valuesA.length
      const lenB = valuesB.length

      // nulls (empty arrays) first
      if (lenA === 0 && lenB !== 0) {
        return -1
      } else if (lenA !== 0 && lenB === 0) {
        return 1
      }

      for (let i = 0; i < Math.max(valuesA.length, valuesB.length); i++) {
        let compared = 0

        const isAdefined = valuesA[i] !== undefined
        const isBdefined = valuesB[i] !== undefined

        if (isAdefined && isBdefined) {
          const isAnull = valuesA[i] === null
          const isBnull = valuesB[i] === null
          if (!isAnull && !isBnull) {
            compared = relatedSortFunc(
              { [name]: valuesA[i] },
              { [name]: valuesB[i] }
            )
          } else if (!isAnull) {
            // Postgres sort nulls last in arrays, so we do the same here.
            compared = order === 'ASC' ? -1 : 1
          } else if (!isBnull) {
            compared = order === 'ASC' ? 1 : -1
          }
        } else if (isAdefined) {
          // Different lengths with the same initial values, the shorter array comes first.
          compared = order === 'ASC' ? 1 : -1
        } else if (isBdefined) {
          compared = order === 'ASC' ? -1 : 1
        }
        if (compared !== 0) {
          return compared
        }
      }

      // The arrays have the same length and all values are the same.
      // Let's compare the order and the id of the linked row items.
      for (let i = 0; i < a[name].length; i++) {
        const orderA = new BigNumber(a[name][i].order)
        const orderB = new BigNumber(b[name][i].order)
        if (!orderA.isEqualTo(orderB)) {
          return order === 'ASC'
            ? orderA.minus(orderB).toNumber()
            : orderB.minus(orderA).toNumber()
        }
      }

      // If the order is the same, we compare the id of the linked row items to
      // match the backend behavior.
      for (let i = 0; i < a[name].length; i++) {
        const aId = a[name][i].id
        const bId = b[name][i].id
        if (aId !== bId) {
          return order === 'ASC' ? aId - bId : bId - aId
        }
      }

      // Exactly the same items. The order will be determined by the next
      // order by in the list, either another field or rows' order and id.
      return 0
    }
  }

  getCanBePrimaryField() {
    return false
  }

  /**
   * The structure for updating is slightly different than what we need for displaying
   * the value because the display value does not have to be included. Here we convert
   * the array[object] structure to an array[id] structure.
   */
  prepareValueForUpdate(field, value) {
    return value.map((item) => {
      if (typeof item === 'object') {
        return item.id === null ? item.value : item.id
      } else {
        return item
      }
    })
  }

  prepareValueForCopy(field, value) {
    if (!Array.isArray(value)) {
      return ''
    }

    const nameList = value.map((link) => {
      if (link.value) {
        return link.value
      }
      return this.app.i18n.t('gridViewFieldLinkRow.unnamed', { value: link.id })
    })

    // Use papa to generate a CSV string
    return this.app.$papa.arrayToString(nameList)
  }

  prepareRichValueForCopy(field, value) {
    return {
      tableId: field.link_row_table_id,
      value,
    }
  }

  checkRichValueIsCompatible(value) {
    return (
      value === null ||
      (typeof value === 'object' &&
        Object.prototype.hasOwnProperty.call(value, 'tableId') &&
        Object.prototype.hasOwnProperty.call(value, 'value') &&
        value.value.every(
          (row) =>
            Object.prototype.hasOwnProperty.call(row, 'id') &&
            Object.prototype.hasOwnProperty.call(row, 'value')
        ))
    )
  }

  prepareValueForPaste(field, clipboardData, richClipboardData) {
    if (
      this.checkRichValueIsCompatible(richClipboardData) &&
      richClipboardData &&
      field.link_row_table_id === richClipboardData.tableId
    ) {
      if (richClipboardData === null) {
        return []
      }
      let value = richClipboardData.value
      // Strip the remaining relationships because the backend will fail when trying
      // to add them and the field doesn't allow it.
      if (!field.link_row_multiple_relationships) {
        value = value.slice(0, 1)
      }
      return value
    } else {
      // Fallback to text version
      try {
        let data = this.app.$papa.stringToArray(clipboardData)
        // Strip the remaining relationships because the backend will fail when trying
        // to add them and the field doesn't allow it.
        if (!field.link_row_multiple_relationships) {
          data = data.slice(0, 1)
        }
        return data.map((name) => ({ id: null, value: name }))
      } catch (e) {
        return []
      }
    }
  }

  prepareValueForDuplicate(field, value) {
    // Strip the remaining values because the backend will fail when trying to add
    // them and the field doesn't allow it.
    if (!field.link_row_multiple_relationships) {
      value = value.slice(0, 1)
    }
    return value
  }

  toHumanReadableString(field, value) {
    if (value) {
      return value.map((link) => link.value).join(', ')
    }
    return ''
  }

  /**
   * When a table is deleted it might be the case that this is the related table of
   * the field. If so it means that this field has already been deleted and it needs
   * to be removed from the store without making an API call.
   */
  tableDeleted({ dispatch }, field, table, database) {
    if (field.link_row_table_id === table.id) {
      dispatch('field/forceDelete', field, { root: true })
    }
  }

  getDocsDataType(field) {
    return 'array'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.linkRow', {
      table: field.link_row_table_id,
    })
  }

  getDocsRequestExample(field) {
    return [1]
  }

  getDocsResponseExample(field) {
    return [
      {
        id: 0,
        value: 'string',
      },
    ]
  }

  canBeReferencedByFormulaField() {
    return true
  }

  shouldFetchFieldSelectOptions() {
    return false
  }

  canParseQueryParameter() {
    return true
  }

  async parseQueryParameter(field, value, { client, slug, publicAuthToken }) {
    const parsedValues = this.app.$papa.stringToArray(value)
    const items = []
    const length =
      field.field_component === DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY
        ? 1
        : parsedValues.length

    for (let i = 0; i < length; i++) {
      const { data } = await ViewService(client).linkRowFieldLookup(
        slug,
        field.field.id,
        1,
        parsedValues[i],
        1,
        publicAuthToken
      )
      const item = data.results.find((item) => item.value === parsedValues[i])

      if (item) {
        items.push(item)
      }
    }

    return items.length > 0 ? items : this.getDefaultValue()
  }

  getCanImport() {
    return true
  }

  isEmpty(field, value) {
    if (super.isEmpty(field, value)) {
      return true
    }

    if (value.some((v) => !Number.isInteger(v.id))) {
      return true
    }

    return false
  }

  shouldRefetchFieldData(field, rows) {
    return rows.some((row) => {
      const fieldValue = row[`field_${field.id}`]
      return (
        fieldValue?.length === LINKED_ITEMS_DEFAULT_LOAD_COUNT &&
        !row._?.fullyLoaded
      )
    })
  }
}

export class NumberFieldType extends FieldType {
  static getMaxNumberLength() {
    return 50
  }

  static getType() {
    return 'number'
  }

  static getIconClass() {
    return 'baserow-icon-hashtag'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.number')
  }

  getFormComponent() {
    return FieldNumberSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldNumber
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldNumber
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldNumber
  }

  getCardComponent() {
    return RowCardFieldNumber
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldNumber
  }

  getFilterInputComponent(field, filterType) {
    return ViewFilterTypeNumber
  }

  getSortIndicator() {
    return ['text', '1', '9']
  }

  getDefaultValueFieldName() {
    return 'number_default'
  }

  getDefaultValue(field, flat) {
    const defaultValueFieldName = this.getDefaultValueFieldName()
    const defaultValue = field[defaultValueFieldName]
    if (defaultValue === null || defaultValue === undefined) {
      return null
    }
    const decimalPlaces = field.number_decimal_places || 0
    return new BigNumber(defaultValue).toFixed(decimalPlaces)
  }

  canUpsert() {
    return true
  }

  /**
   * When searching a cell's value, this should return the value to match the user's
   * search term against. We can't use `toHumanReadableString` here as it needs to be
   * consistent with the backend, and the backend doesn't know about the formatting
   * that `toHumanReadableString` uses.
   */
  toSearchableString(field, value, delimiter = ', ') {
    return value ? String(value) : ''
  }

  getSort(name, order) {
    return (a, b) => {
      if (a[name] === b[name]) {
        return 0
      }

      if (
        (a[name] === null && order === 'ASC') ||
        (b[name] === null && order === 'DESC')
      ) {
        return -1
      }

      if (
        (b[name] === null && order === 'ASC') ||
        (a[name] === null && order === 'DESC')
      ) {
        return 1
      }

      const numberA = new BigNumber(a[name])
      const numberB = new BigNumber(b[name])

      return order === 'ASC'
        ? numberA.minus(numberB).toNumber()
        : numberB.minus(numberA).toNumber()
    }
  }

  getValidationError(field, value) {
    if (value === null || value === '') {
      return null
    }

    const nrValue = new BigNumber(value)
    if (nrValue.isNaN() || !nrValue.isFinite()) {
      return this.app.i18n.t('fieldErrors.invalidNumber')
    }
    const maxVal = new BigNumber(`10e${NumberFieldType.getMaxNumberLength()}`)
    if (nrValue.absoluteValue().isGreaterThanOrEqualTo(maxVal)) {
      return this.app.i18n.t('fieldErrors.maxDigits', {
        max: NumberFieldType.getMaxNumberLength(),
      })
    }
    return null
  }

  /**
   * First checks if the value is numeric, if that is the case, the number is going
   * to be formatted.
   */
  prepareValueForPaste(field, clipboardData, richClipboardData) {
    let value = clipboardData
    const parsedRichValue =
      richClipboardData != null ? new BigNumber(richClipboardData) : null
    if (parsedRichValue !== null && !parsedRichValue.isNaN()) {
      value = parsedRichValue
    }
    return this.parseInputValue(field, value)
  }

  prepareValueForCopy(field, value) {
    return NumberFieldType.formatNumber(field, new BigNumber(value))
  }

  prepareRichValueForCopy(field, value) {
    return new BigNumber(value).toString()
  }

  /**
   * Formats the value based on the field's settings. The number will be rounded
   * if too much decimal places are provided and if negative numbers aren't allowed
   * they will be set to 0.
   */
  static formatNumber(field, value) {
    return formatNumberValue(field, value)
  }

  toHumanReadableString(field, value, delimiter = ', ') {
    return formatDecimalNumber(field, value)
  }

  getDocsDataType(field) {
    return field.number_decimal_places > 0 ? 'decimal' : 'number'
  }

  getDocsDescription(field) {
    let t = field.number_decimal_places === 0 ? 'number' : 'decimal'
    if (!field.number_negative) {
      t += 'Positive'
    }
    return this.app.i18n.t(`fieldDocs.${t}`, {
      places: field.number_decimal_places,
    })
  }

  getDocsRequestExample(field) {
    if (field.number_decimal_places > 0) {
      let number = '0.'
      for (let i = 1; i <= field.number_decimal_places; i++) {
        number += '0'
      }
      return number
    }
    return 0
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canParseQueryParameter() {
    return true
  }

  parseQueryParameter(field, value) {
    return NumberFieldType.formatNumber(field.field, value)
  }

  getCanImport() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }

  parseInputValue(field, value) {
    return parseNumberValue(field, value)
  }

  prepareValueForUpdate(field, value) {
    return parseNumberValue(field, value)
  }

  parseFromLinkedRowItemValue(field, value) {
    if (value === '') {
      return null
    }
    return new BigNumber(value)
  }

  parseFilterValue(field, value) {
    const res = parseNumberValue(field, String(value ?? ''), false)
    return res === null || res.isNaN() ? '' : res.toString()
  }

  canHaveDbIndex(fieldValues) {
    return true
  }
}

BigNumber.config({ EXPONENTIAL_AT: NumberFieldType.getMaxNumberLength() })

export class RatingFieldType extends FieldType {
  static getMaxNumberLength() {
    return 2
  }

  static getType() {
    return 'rating'
  }

  static getIconClass() {
    return 'iconoir-star'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.rating')
  }

  getFormComponent() {
    return FieldRatingSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldRating
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldRating
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldRating
  }

  getCardComponent() {
    return RowCardFieldRating
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldText
  }

  getSortIndicator() {
    return ['text', '1', '9']
  }

  getDefaultValueFieldName() {
    return 'rating_default'
  }

  getDefaultValue(field, flat) {
    return 0
  }

  getEmptyValue(field) {
    return 0
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      if (a[name] === b[name]) {
        return 0
      }

      const numberA = a[name]
      const numberB = b[name]

      return order === 'ASC'
        ? numberA < numberB
          ? -1
          : 1
        : numberB < numberA
        ? -1
        : 1
    }
  }

  /**
   * First checks if the value is numeric, if that is the case, the number is going
   * to be formatted.
   */
  prepareValueForPaste(field, clipboardData) {
    const pastedValue = clipboardData
    const value = parseInt(pastedValue, 10)

    if (isNaN(value) || !isFinite(value)) {
      return 0
    }

    // Clamp the value
    if (value < 0) {
      return 0
    }
    if (value > field.max_value) {
      return field.max_value
    }
    return value
  }

  getDocsDataType(field) {
    return 'number'
  }

  getDocsDescription(field) {
    return this.app.i18n.t(`fieldDocs.rating`)
  }

  getDocsRequestExample(field) {
    return 3
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canParseQueryParameter() {
    return true
  }

  parseQueryParameter(field, value) {
    const valueParsed = parseInt(value, 10)

    if (isNaN(valueParsed) || valueParsed < 0) {
      return this.getDefaultValue()
    }

    if (valueParsed > field.max_value) {
      return field.max_value
    }

    return valueParsed
  }

  getCanImport() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }

  canHaveDbIndex(fieldValues) {
    return true
  }
}

export class BooleanFieldType extends FieldType {
  static getType() {
    return 'boolean'
  }

  static getIconClass() {
    return 'baserow-icon-circle-checked'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.boolean')
  }

  getAlias() {
    return 'checkbox'
  }

  getFormComponent() {
    return FieldBooleanSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldBoolean
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldBoolean
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldBoolean
  }

  getCardComponent() {
    return RowCardFieldBoolean
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldBoolean
  }

  getEmptyValue(field) {
    return false
  }

  getDefaultValueFieldName() {
    return 'boolean_default'
  }

  getDefaultValue(field, flat) {
    const defaultValueFieldName = this.getDefaultValueFieldName()
    return field[defaultValueFieldName] || this.getEmptyValue(field)
  }

  getSortIndicator() {
    return ['icon', 'baserow-icon-circle-empty', 'baserow-icon-circle-checked']
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const intA = +a[name]
      const intB = +b[name]
      return order === 'ASC' ? intA - intB : intB - intA
    }
  }

  toHumanReadableString(field, value) {
    if (typeof value === 'boolean') {
      return `${value}`
    }

    return super.toHumanReadableString(field, value)
  }

  /**
   * Check if the clipboard data text contains a string that might indicate if the
   * value is true.
   */
  prepareValueForPaste(field, clipboardData) {
    if (!clipboardData) {
      clipboardData = ''
    }
    const value = clipboardData.toLowerCase().trim()
    return this._prepareValue(value)
  }

  _prepareValue(value) {
    return trueValues.includes(value)
  }

  parseInputValue(field, value) {
    return this._prepareValue(value)
  }

  parseFromLinkedRowItemValue(field, value) {
    return this._prepareValue(value)
  }

  getDocsDataType(field) {
    return 'boolean'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.boolean')
  }

  getDocsRequestExample(field) {
    return true
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canParseQueryParameter() {
    return true
  }

  parseQueryParameter(field, value) {
    return value === 'true'
  }

  getCanImport() {
    return true
  }

  toSearchableString(field, value, delimiter = ', ') {
    return value ? 'true' : 'false'
  }

  getCanGroupByInView(field) {
    return true
  }

  getHasValueEqualFilterFunction(field, negate = false) {
    const that = this
    return (cellValue, filterValue) => {
      const value = that._prepareValue(filterValue)
      const out = genericHasValueEqualFilter(cellValue, value)
      if (negate) {
        return filterValue === '' || !out
      }
      return filterValue === '' || out
    }
  }

  getHasNotValueEqualFilterFunction(field) {
    return this.getHasValueEqualFilterFunction(field, true)
  }

  parseFilterValue(field, value) {
    return this.parseInputValue(field, String(value ?? ''))
  }

  canHaveDbIndex(fieldValues) {
    return true
  }
}

class BaseDateFieldType extends FieldType {
  static getIconClass() {
    return 'iconoir-calendar'
  }

  getSortIndicator() {
    return ['text', '1', '9']
  }

  getFormComponent() {
    return FieldDateSubForm
  }

  getCardComponent() {
    return RowCardFieldDate
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldDate
  }

  getSort(name, order) {
    return (a, b) => {
      if (moment.isMoment(a[name]) && moment.isMoment(b[name])) {
        return order === 'ASC' ? a[name].diff(b[name]) : b[name].diff(a[name])
      }

      if (a[name] === b[name]) {
        return 0
      }

      if (
        (a[name] === null && order === 'ASC') ||
        (b[name] === null && order === 'DESC')
      ) {
        return -1
      }

      if (
        (b[name] === null && order === 'ASC') ||
        (a[name] === null && order === 'DESC')
      ) {
        return 1
      }

      const timeA = new Date(a[name]).getTime()
      const timeB = new Date(b[name]).getTime()

      return order === 'ASC' ? (timeA < timeB ? -1 : 1) : timeB < timeA ? -1 : 1
    }
  }

  toHumanReadableString(field, value) {
    return this._toFormattedString(field, value)
  }

  _toFormattedString(field, value, guess = true) {
    const timezone = getFieldTimezone(field, guess)
    const date = moment.utc(value)
    if (timezone !== null) {
      date.tz(timezone)
    }

    if (date.isValid()) {
      const dateFormat = getDateMomentFormat(field.date_format)
      let dateString = date.format(dateFormat)

      if (field.date_include_time) {
        const timeFormat = getTimeMomentFormat(field.date_time_format)
        dateString = `${dateString} ${date.format(timeFormat)}`
      }
      return dateString
    } else {
      return ''
    }
  }

  toSearchableString(field, value, delimiter = ', ') {
    return this._toFormattedString(field, value, false)
  }

  prepareValueForCopy(field, value) {
    return this.toHumanReadableString(field, value)
  }

  prepareRichValueForCopy(field, value) {
    return value
  }

  /**
   * Tries to parse the clipboard text value with moment and returns the date in the
   * correct format for the field. If it can't be parsed null is returned.
   */
  prepareValueForPaste(field, clipboardData, richClipboardData) {
    const dateValue = this.parseInputValue(field, clipboardData || '')
    return this.formatValue(field, dateValue)
  }

  /**
   * Tries to return the minimum amount of date formats that are needed to parse
   * a given date string.
   * @param {*} field the date field
   * @param {*} value the date string to parse
   * @returns List of date formats
   */
  static getDateFormatsOptionsForValue(field, value) {
    let formats = [moment.ISO_8601]

    const timeFormats = value?.includes(':')
      ? ['', ' H:m', ' H:m A', ' H:m:s', ' H:m:s A']
      : ['']

    const getDateTimeFormatsFor = (...dateFormats) => {
      return dateFormats.flatMap((df) => timeFormats.map((tf) => `${df}${tf}`))
    }

    const containsDash = value?.includes('-')
    const s = containsDash ? '-' : '/'

    const usFieldFormats = getDateTimeFormatsFor(
      `M${s}D${s}YYYY`,
      `YYYY${s}D${s}M`
    )
    const euFieldFormats = getDateTimeFormatsFor(
      `D${s}M${s}YYYY`,
      `YYYY${s}M${s}D`
    )
    if (field.date_format === 'US') {
      formats = formats.concat(usFieldFormats).concat(euFieldFormats)
    } else {
      formats = formats.concat(euFieldFormats).concat(usFieldFormats)
    }
    return formats
  }

  parseInputValue(field, dateString) {
    const formats = DateFieldType.getDateFormatsOptionsForValue(
      field,
      dateString
    )

    let date = moment.utc(dateString, formats, true)
    if (!date.isValid()) {
      // guessFormat can understand different separators and many more formats,
      // so let's give it a chance to guess the date from dateString.
      try {
        const guessedFormats = guessFormat(dateString)
        date = moment.utc(dateString, guessedFormats, true)
      } catch (e) {
        // date will still be invalid
      }
      if (!date.isValid()) {
        return null
      }
    }
    const timezone = getFieldTimezone(field)
    if (timezone) {
      date.tz(timezone, true)
    }
    return date
  }

  parseFromLinkedRowItemValue(field, value) {
    return this.parseInputValue(field, value)
  }

  formatValue(field, value) {
    const momentDate = moment.utc(value)
    if (momentDate.isValid()) {
      return field.date_include_time
        ? momentDate.format()
        : momentDate.format('YYYY-MM-DD')
    } else {
      return null
    }
  }

  getDocsDataType(field) {
    return 'date'
  }

  getDocsDescription(field) {
    return field.date_include_time
      ? this.app.i18n.t('fieldDocs.dateTime')
      : this.app.i18n.t('fieldDocs.date')
  }

  getDocsRequestExample(field) {
    return field.date_include_time ? '2020-01-01T12:00:00Z' : '2020-01-01'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  getCanImport() {
    return true
  }

  canRepresentDate(field) {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }

  isEqual(field, value1, value2) {
    if (field.date_include_time) {
      // Seconds are visually ignored for a field that includes the time, so we'd
      // have to compare the values without them. A date is normally `null` or
      // `2023-10-27T18:17:00.758266Z`, and if you only take the first 16
      // characters, it's the value without the seconds.
      return (
        ('' + value1).substring(0, 16) ===
        ('' + value2).toString().substring(0, 16)
      )
    }
    return super.isEqual(field, value1, value2)
  }

  toBaserowFormulaType(field) {
    return 'date'
  }

  canHaveDbIndex(fieldValues) {
    return true
  }
}

export class DateFieldType extends BaseDateFieldType {
  static getType() {
    return 'date'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.date')
  }

  getGridViewFieldComponent() {
    return GridViewFieldDate
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldDate
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldDate
  }

  canParseQueryParameter() {
    return true
  }

  canUpsert() {
    return true
  }

  parseQueryParameter(field, value) {
    return this.formatValue(
      field.field,
      this.parseInputValue(field.field, value)
    )
  }
}

export class CreatedOnLastModifiedBaseFieldType extends BaseDateFieldType {
  isReadOnlyField() {
    return true
  }

  getFormComponent() {
    return FieldDateSubForm
  }

  getFormViewFieldComponents(field) {
    return {}
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldDateReadOnly
  }

  getGridViewFieldComponent() {
    return GridViewFieldDateReadOnly
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldDate
  }

  /**
   * The "new row" value for the new row in the case of LastModified or CreatedOn Fields
   * is simply the current time.
   */
  getNewRowValue() {
    return moment().local().format()
  }

  shouldFetchDataWhenAdded() {
    return true
  }

  getDocsDataType(field) {
    return null
  }

  getDocsDescription(field, firstPartOverwrite) {
    const firstPart =
      firstPartOverwrite || this.app.i18n.t('fieldDocs.readOnly')
    return field.date_include_time
      ? `${firstPart} ${this.app.i18n.t('fieldDocs.dateTimeResponse')}`
      : `${firstPart} ${this.app.i18n.t('fieldDocs.dateResponse')}`
  }

  getDocsRequestExample(field) {
    return field.date_include_time ? '2020-01-01T12:00:00Z' : '2020-01-01'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }
}

export class LastModifiedFieldType extends CreatedOnLastModifiedBaseFieldType {
  static getType() {
    return 'last_modified'
  }

  static getIconClass() {
    return 'iconoir-edit'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.lastModified')
  }

  getAlias() {
    return 'last updated'
  }

  getDocsDescription(field) {
    return super.getDocsDescription(
      field,
      this.app.i18n.t('fieldDocs.lastModifiedReadOnly')
    )
  }

  _onRowChangeOrMove() {
    return moment().utc().format()
  }

  onRowChange(row, currentField, currentFieldValue) {
    return this._onRowChangeOrMove()
  }

  onRowMove(row, order, oldOrder, currentField, currentFieldValue) {
    return this._onRowChangeOrMove()
  }
}

export class CreatedOnFieldType extends CreatedOnLastModifiedBaseFieldType {
  static getType() {
    return 'created_on'
  }

  static getIconClass() {
    return 'iconoir-plus'
  }

  getDocsDescription(field) {
    return super.getDocsDescription(
      field,
      this.app.i18n.t('fieldDocs.createdOnReadOnly')
    )
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.createdOn')
  }
}

export class LastModifiedByFieldType extends FieldType {
  static getType() {
    return 'last_modified_by'
  }

  static getIconClass() {
    return 'iconoir-user'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.lastModifiedBy')
  }

  getAlias() {
    return 'last updated by'
  }

  getFormViewFieldComponents(field) {
    return {}
  }

  isReadOnlyField() {
    return true
  }

  shouldFetchDataWhenAdded() {
    return true
  }

  getGridViewFieldComponent() {
    return GridViewFieldLastModifiedBy
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldLastModifiedBy
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldLastModifiedBy
  }

  getCardComponent() {
    return RowCardFieldLastModifiedBy
  }

  getCanSortInView(field) {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      let userNameA = a[name] === null ? '' : a[name].name
      let userNameB = b[name] === null ? '' : b[name].name

      const workspaces = this.app.store.getters['workspace/getAll']
      const workspaceAvailable = workspaces.length > 0
      if (workspaceAvailable) {
        if (a[name] !== null) {
          const workspaceUserA = this.app.store.getters[
            'workspace/getUserById'
          ](a[name].id)
          userNameA = workspaceUserA ? workspaceUserA.name : userNameA
        }

        if (b[name] !== null) {
          const workspaceUserB = this.app.store.getters[
            'workspace/getUserById'
          ](b[name].id)
          userNameB = workspaceUserB ? workspaceUserB.name : userNameB
        }
      }

      return collatedStringCompare(userNameA, userNameB, order)
    }
  }

  canBeReferencedByFormulaField() {
    return false
  }

  _getCurrentUserValue() {
    return {
      id: this.app.store.getters['auth/getUserId'],
      name: this.app.store.getters['auth/getName'],
    }
  }

  getNewRowValue() {
    return this._getCurrentUserValue()
  }

  onRowChange(row, currentField, currentFieldValue) {
    return this._getCurrentUserValue()
  }

  prepareValueForCopy(field, value) {
    if (value === undefined || value === null) {
      return ''
    }

    const name = value.name

    const workspaces = this.app.store.getters['workspace/getAll']
    if (workspaces.length > 0) {
      const workspaceUser = this.app.store.getters['workspace/getUserById'](
        value.id
      )
      return workspaceUser ? workspaceUser.name : name
    }

    return name
  }

  toHumanReadableString(field, value, delimiter = ', ') {
    return this.prepareValueForCopy(field, value)
  }

  toSearchableString(field, value, delimiter = ', ') {
    return this.toHumanReadableString(field, value, delimiter)
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  getDocsDataType(field) {
    return 'object'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.lastModifiedBy')
  }

  getDocsRequestExample() {
    return {
      id: 1,
      name: 'John',
    }
  }

  toAggregationString(field, value) {
    return value
  }
}

export class CreatedByFieldType extends FieldType {
  static getType() {
    return 'created_by'
  }

  static getIconClass() {
    return 'iconoir-user'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.createdBy')
  }

  getFormViewFieldComponents(field) {
    return {}
  }

  isReadOnlyField() {
    return true
  }

  shouldFetchDataWhenAdded() {
    return true
  }

  getGridViewFieldComponent() {
    return GridViewFieldLastModifiedBy
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldLastModifiedBy
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldLastModifiedBy
  }

  getCardComponent() {
    return RowCardFieldLastModifiedBy
  }

  getCanSortInView(field) {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      let userNameA = a[name] === null ? '' : a[name].name
      let userNameB = b[name] === null ? '' : b[name].name

      const workspaces = this.app.store.getters['workspace/getAll']
      const workspaceAvailable = workspaces.length > 0
      if (workspaceAvailable) {
        if (a[name] !== null) {
          const workspaceUserA = this.app.store.getters[
            'workspace/getUserById'
          ](a[name].id)
          userNameA = workspaceUserA ? workspaceUserA.name : userNameA
        }

        if (b[name] !== null) {
          const workspaceUserB = this.app.store.getters[
            'workspace/getUserById'
          ](b[name].id)
          userNameB = workspaceUserB ? workspaceUserB.name : userNameB
        }
      }

      return collatedStringCompare(userNameA, userNameB, order)
    }
  }

  canBeReferencedByFormulaField() {
    return false
  }

  _getCurrentUserValue() {
    return {
      id: this.app.store.getters['auth/getUserId'],
      name: this.app.store.getters['auth/getName'],
    }
  }

  getNewRowValue() {
    return this._getCurrentUserValue()
  }

  onRowChange(row, currentField, currentFieldValue) {
    return currentFieldValue
  }

  prepareValueForCopy(field, value) {
    if (value === undefined || value === null) {
      return ''
    }

    const name = value.name

    const workspaces = this.app.store.getters['workspace/getAll']
    if (workspaces.length > 0) {
      const workspaceUser = this.app.store.getters['workspace/getUserById'](
        value.id
      )
      return workspaceUser ? workspaceUser.name : name
    }

    return name
  }

  toHumanReadableString(field, value, delimiter = ', ') {
    return this.prepareValueForCopy(field, value)
  }

  toSearchableString(field, value, delimiter = ', ') {
    return this.toHumanReadableString(field, value, delimiter)
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  getDocsDataType(field) {
    return 'object'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.createdBy')
  }

  getDocsRequestExample() {
    return {
      id: 1,
      name: 'John',
    }
  }

  toAggregationString(field, value) {
    return value
  }
}

export class DurationFieldType extends FieldType {
  static getType() {
    return 'duration'
  }

  getCardComponent() {
    return RowCardFieldDuration
  }

  static getIconClass() {
    return 'iconoir-clock-rotate-right'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.duration')
  }

  getDocsDataType(field) {
    return 'duration'
  }

  getDocsRequestExample(field) {
    return DURATION_FORMATS.get(field.duration_format).example
  }

  canBeReferencedByFormulaField() {
    return true
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.duration', {
      format: field.duration_format,
    })
  }

  getFormComponent() {
    return FieldDurationSubForm
  }

  canParseQueryParameter() {
    return true
  }

  parseQueryParameter(field, value, options) {
    return this.parseInputValue(field.field, value)
  }

  toSearchableString(field, value, delimiter = ', ') {
    return this.formatValue(field, value)
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const aValue = a[name]
      const bValue = b[name]

      if (aValue === bValue) {
        return 0
      }

      if (order === 'ASC') {
        return aValue === null || (bValue !== null && aValue < bValue) ? -1 : 1
      } else {
        return bValue === null || (aValue !== null && bValue < aValue) ? -1 : 1
      }
    }
  }

  getSortIndicator() {
    return ['text', '1', '9']
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldDuration
  }

  getGridViewFieldComponent() {
    return GridViewFieldDuration
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldDuration
  }

  getFilterInputComponent(field, filterType) {
    return ViewFilterTypeDuration
  }

  getCanImport() {
    return true
  }

  getValidationError(field, value) {
    if (value === null || value === undefined || value === '') {
      return null
    }

    let totalSecs
    try {
      totalSecs = parseDurationValue(value, field.duration_format)
    } catch (e) {
      totalSecs = null
    }

    if (totalSecs === null) {
      return this.app.i18n.t('fieldErrors.invalidDuration', {
        durationFormat: this.getDocsRequestExample(field),
      })
    } else if (
      totalSecs > MAX_BACKEND_DURATION_VALUE_NUMBER_OF_SECS ||
      totalSecs < MIN_BACKEND_DURATION_VALUE_NUMBER_OF_SECS
    ) {
      return this.app.i18n.t('fieldErrors.overflowDuration')
    }
    return null
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldDuration
  }

  formatValue(field, value) {
    return formatDurationValue(value, field.duration_format)
  }

  parseInputValue(field, value) {
    const format = field.duration_format
    const preparedValue = parseDurationValue(value, format)
    return roundDurationValueToFormat(preparedValue, format)
  }

  parseFromLinkedRowItemValue(field, value) {
    return this.parseInputValue(field, value)
  }

  toHumanReadableString(field, value, delimiter = ', ') {
    return this.formatValue(field, value)
  }

  prepareValueForCopy(field, value) {
    return this.formatValue(field, value)
  }

  prepareRichValueForCopy(field, value) {
    return value
  }

  prepareValueForPaste(field, clipboardData, richClipboardData) {
    if (richClipboardData && isInteger(richClipboardData)) {
      return richClipboardData
    }
    return this.parseInputValue(field, clipboardData)
  }

  getCanGroupByInView(field) {
    return true
  }
}

export class URLFieldType extends FieldType {
  static getType() {
    return 'url'
  }

  static getIconClass() {
    return 'iconoir-link'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.url')
  }

  getGridViewFieldComponent() {
    return GridViewFieldURL
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldURL
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldURL
  }

  getCardComponent() {
    return RowCardFieldURL
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldText
  }

  prepareValueForPaste(field, clipboardData) {
    const value = clipboardData
    return isValidURL(value) ? value : ''
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const stringA = a[name] === null ? '' : '' + a[name]
      const stringB = b[name] === null ? '' : '' + b[name]

      return collatedStringCompare(stringA, stringB, order)
    }
  }

  getDefaultValue(field, flat) {
    return ''
  }

  getValidationError(field, value) {
    if (value === null || value === '') {
      return null
    }
    if (!isValidURL(value)) {
      return this.app.i18n.t('fieldErrors.invalidUrl')
    }
    return null
  }

  getDocsDataType(field) {
    return 'string'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.url')
  }

  getDocsRequestExample(field) {
    return 'https://baserow.io'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  getContainsWordFilterFunction(field) {
    return genericContainsWordFilter
  }

  canParseQueryParameter() {
    return true
  }

  canBeReferencedByFormulaField() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }

  getCanImport() {
    return true
  }
}

export class EmailFieldType extends FieldType {
  static getType() {
    return 'email'
  }

  static getIconClass() {
    return 'iconoir-mail'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.email')
  }

  getGridViewFieldComponent() {
    return GridViewFieldEmail
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldURL
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldEmail
  }

  getCardComponent() {
    return RowCardFieldEmail
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldText
  }

  prepareValueForPaste(field, clipboardData) {
    const value = clipboardData
    return isValidEmail(value) ? value : ''
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const stringA = a[name] === null ? '' : '' + a[name]
      const stringB = b[name] === null ? '' : '' + b[name]

      return collatedStringCompare(stringA, stringB, order)
    }
  }

  getDefaultValue(field, flat) {
    return ''
  }

  getValidationError(field, value) {
    if (value === null || value === '' || value === undefined) {
      return null
    }
    if (value.length > 254) {
      return this.app.i18n.t('fieldErrors.max254Chars')
    }
    if (!isValidEmail(value)) {
      return this.app.i18n.t('fieldErrors.invalidEmail')
    }
    return null
  }

  getDocsDataType(field) {
    return 'string'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.email')
  }

  getDocsRequestExample(field) {
    return 'example@baserow.io'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  getContainsWordFilterFunction(field) {
    return genericContainsWordFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canParseQueryParameter() {
    return true
  }

  getCanImport() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }
}

export class FileFieldType extends FieldType {
  fileRegex = /^(.+\.[^\s]+) \(http[^)]+\/([^\s]+.[^\s]+)\)$/
  fileURLRegex = /^http[^)]+\/([^\s]+.[^\s]+)$/

  static getType() {
    return 'file'
  }

  getEmptyValue(field) {
    return []
  }

  static getIconClass() {
    return 'iconoir-empty-page'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.file')
  }

  getAlias() {
    return 'upload attachment document'
  }

  getGridViewFieldComponent() {
    return GridViewFieldFile
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldFile
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldFile
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldFile
  }

  getFormViewFieldComponents(field, { $store, $client, slug }) {
    const components = super.getFormViewFieldComponents(field)
    const userFileUploadTypes = [UploadFileUserFileUploadType.getType()]
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].properties = {
      userFileUploadTypes,
      uploadFile: (file, progress) => {
        return FormService($client).uploadFile(
          file,
          progress,
          slug,
          $store.getters['page/view/public/getAuthToken']
        )
      },
    }
    return components
  }

  getCardComponent() {
    return RowCardFieldFile
  }

  toHumanReadableString(field, value) {
    return value.map((file) => file.visible_name).join(', ')
  }

  prepareValueForCopy(field, value) {
    if (value === undefined || value === null) {
      return ''
    }

    return this.app.$papa.arrayToString(
      value.map(
        ({ url, visible_name: visibleName }) => `${visibleName} (${url})`
      )
    )
  }

  prepareRichValueForCopy(field, value) {
    return value
  }

  checkRichValueIsCompatible(values) {
    return (
      Array.isArray(values) &&
      values.every(
        (value) =>
          Object.prototype.hasOwnProperty.call(value, 'name') ||
          Object.prototype.hasOwnProperty.call(value, 'url')
      )
    )
  }

  prepareValueForPaste(field, clipboardData, richClipboardData) {
    if (this.checkRichValueIsCompatible(richClipboardData)) {
      return richClipboardData
        .map((file) => {
          if (Object.prototype.hasOwnProperty.call(file, 'name')) {
            return file
          } else if (isValidURL(file.url)) {
            const name = getFilenameFromUrl(file.url)
            return { ...file, name }
          } else {
            return null
          }
        })
        .filter((f) => f)
    } else {
      try {
        const files = this.app.$papa.stringToArray(clipboardData)
        return files
          .map((strValue) => {
            // Try to match the expected format
            const matches = strValue.match(this.fileRegex)
            if (matches) {
              return {
                name: matches[2],
                visible_name: matches[1],
              }
            } else {
              return null
            }
          })
          .filter((v) => v)
      } catch {
        return []
      }
    }
  }

  getDefaultValue(field, flat) {
    return []
  }

  getCanSortInView(field) {
    return false
  }

  getDocsDataType() {
    return 'array'
  }

  getDocsDescription() {
    return this.app.i18n.t('fieldDocs.file')
  }

  getDocsRequestExample() {
    return [
      {
        name: 'VXotniBOVm8tbstZkKsMKbj2Qg7KmPvn_39d354a76abe56baaf569ad87d0333f58ee4bf3eed368e3b9dc736fd18b09dfd.png',
      },
    ]
  }

  getDocsResponseExample() {
    return [
      {
        url: 'https://files.baserow.io/user_files/VXotniBOVm8tbstZkKsMKbj2Qg7KmPvn_39d354a76abe56baaf569ad87d0333f58ee4bf3eed368e3b9dc736fd18b09dfd.png',
        thumbnails: {
          tiny: {
            url: 'https://files.baserow.io/media/thumbnails/tiny/VXotniBOVm8tbstZkKsMKbj2Qg7KmPvn_39d354a76abe56baaf569ad87d0333f58ee4bf3eed368e3b9dc736fd18b09dfd.png',
            width: 21,
            height: 21,
          },
          small: {
            url: 'https://files.baserow.io/media/thumbnails/small/VXotniBOVm8tbstZkKsMKbj2Qg7KmPvn_39d354a76abe56baaf569ad87d0333f58ee4bf3eed368e3b9dc736fd18b09dfd.png',
            width: 48,
            height: 48,
          },
        },
        name: 'VXotniBOVm8tbstZkKsMKbj2Qg7KmPvn_39d354a76abe56baaf569ad87d0333f58ee4bf3eed368e3b9dc736fd18b09dfd.png',
        size: 229940,
        mime_type: 'image/png',
        is_image: true,
        image_width: 1280,
        image_height: 585,
        uploaded_at: '2020-11-17T12:16:10.035234+00:00',
      },
    ]
  }

  getContainsFilterFunction() {
    return filenameContainsFilter
  }

  shouldFetchFieldSelectOptions() {
    return false
  }

  getCanImport() {
    return true
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canRepresentFiles(field) {
    return true
  }
}

export class SingleSelectFieldType extends SelectOptionBaseFieldType {
  static getType() {
    return 'single_select'
  }

  static getIconClass() {
    return 'baserow-icon-single-select'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.singleSelect')
  }

  getFormComponent() {
    return FieldSingleSelectOptionsSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldSingleSelect
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldSingleSelect
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldSingleSelect
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldSingleSelect
  }

  getFormViewFieldComponents(field) {
    const { i18n } = this.app
    const components = super.getFormViewFieldComponents(field)
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].name = i18n.t(
      'fieldType.singleSelectDropdown'
    )
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].properties = {
      'allow-create-options': false,
    }
    components.radios = {
      name: i18n.t('fieldType.singleSelectRadios'),
      component: FormViewFieldSingleSelectRadios,
      properties: {},
    }
    return components
  }

  getCardComponent() {
    return RowCardFieldSingleSelect
  }

  getSort(name, order) {
    return (a, b) => {
      const stringA = a[name] === null ? '' : '' + a[name].value
      const stringB = b[name] === null ? '' : '' + b[name].value
      return collatedStringCompare(stringA, stringB, order)
    }
  }

  getSortByOptionOrder(name, order, field) {
    const getOrder = function (row, name, field) {
      let id = null

      try {
        id = row[name].id || null
      } catch (e) {
        return -1
      }

      return field.select_options.findIndex((o) => o.id === id) || -1
    }

    return (a, b) => {
      const aOrder = getOrder(a, name, field)
      const bOrder = getOrder(b, name, field)

      if (order === 'ASC') {
        return aOrder - bOrder
      } else if (order === 'DESC') {
        return bOrder - aOrder
      }
    }
  }

  getSortTypes(field) {
    const defaultTypes = super.getSortTypes(field)
    defaultTypes.order = {
      function: this.getSortByOptionOrder,
      indicator: ['text', 'First', 'Last'],
    }
    return defaultTypes
  }

  parseFromLinkedRowItemValue(field, value) {
    return value ? { value } : null
  }

  prepareValueForUpdate(field, value) {
    if (value === undefined || value === null) {
      return null
    }
    return value.id
  }

  prepareValueForCopy(field, value) {
    if (value === undefined || value === null) {
      return ''
    }
    return value.value
  }

  prepareRichValueForCopy(field, value) {
    if (value === undefined) {
      return null
    }
    return value
  }

  _findOptionWithMatchingId(field, rawTextValue) {
    if (isInteger(rawTextValue)) {
      const pastedOptionId = parseInt(rawTextValue, 10)
      return field.select_options.find((option) => option.id === pastedOptionId)
    }
    return undefined
  }

  _findOptionWithMatchingValue(field, rawTextValue) {
    const trimmedPastedText = rawTextValue.trim()
    return field.select_options.find(
      (option) => option.value === trimmedPastedText
    )
  }

  checkRichValueIsCompatible(value) {
    return (
      value === null ||
      (typeof value === 'object' &&
        Object.prototype.hasOwnProperty.call(value, 'id'))
    )
  }

  prepareValueForPaste(field, clipboardData, richClipboardData) {
    if (this.checkRichValueIsCompatible(richClipboardData)) {
      if (richClipboardData === null) {
        return null
      }
      return this._findOptionWithMatchingId(field, richClipboardData.id)
    } else {
      if (!clipboardData) {
        return null
      }
      return (
        this._findOptionWithMatchingId(field, clipboardData) ||
        this._findOptionWithMatchingValue(field, clipboardData)
      )
    }
  }

  toHumanReadableString(field, value) {
    if (value === undefined || value === null) {
      return ''
    }
    return value.value
  }

  toAggregationString(field, value) {
    return value
  }

  getDocsDataType() {
    return 'number'
  }

  getDocsDescription(field) {
    const options = field.select_options
      .map(
        (option) =>
          // @TODO move this template to a component.
          `<div class="select-options-listing">
              <div class="select-options-listing__id">${option.id}</div>
              <div class="select-options-listing__value background-color--${option.color}">${option.value}</div>
           </div>
          `
      )
      .join('\n')

    return `
      ${this.app.i18n.t('fieldDocs.singleSelect')}
      <br />
      ${options}
    `
  }

  getDocsRequestExample() {
    return 1
  }

  getDocsResponseExample() {
    return {
      id: 1,
      value: 'Option',
      color: 'light-blue',
    }
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  getContainsWordFilterFunction(field) {
    return genericContainsWordFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  shouldFetchFieldSelectOptions() {
    return false
  }

  canParseQueryParameter() {
    return true
  }

  parseQueryParameter(field, value) {
    const selectedOption = field.field.select_options.find(
      (option) => option.value === value
    )

    return selectedOption ?? this.getDefaultValue(field)
  }

  getCanImport() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }

  getGroupValueFromRowValue(field, value) {
    return value ? value.id : null
  }

  getRowValueFromGroupValue(field, value) {
    return value ? { id: value } : null
  }

  isEqual(field, value1, value2) {
    const value1Id = value1?.id || null
    const value2Id = value2?.id || null
    return value1Id === value2Id
  }

  getDefaultValueFieldName() {
    return 'single_select_default'
  }

  getDefaultValue(field, flat) {
    const defaultValueFieldName = this.getDefaultValueFieldName()
    const defaultValue = field[defaultValueFieldName]
    if (defaultValue != null) {
      const defaultValueOption = field.select_options.find(
        (option) => option.id === defaultValue
      )
      if (defaultValueOption) {
        return flat ? defaultValue : defaultValueOption
      }
    }
    return this.getEmptyValue(field)
  }
}

export class MultipleSelectFieldType extends SelectOptionBaseFieldType {
  static getType() {
    return 'multiple_select'
  }

  static getIconClass() {
    return 'iconoir-list'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.multipleSelect')
  }

  getFormComponent() {
    return FieldMultipleSelectOptionsSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldMultipleSelect
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldMultipleSelect
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldMultipleSelect
  }

  parseFromLinkedRowItemValue(field, value) {
    // FIXME: what if the option value contains a comma?
    return value.split(',').map((value) => ({ value: value.trim() }))
  }

  getFormViewFieldComponents(field) {
    const { i18n } = this.app
    const components = super.getFormViewFieldComponents(field)
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].properties = {
      'allow-create-options': false,
    }
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].name = i18n.t(
      'fieldType.multipleSelectDropdown'
    )
    components.checkboxes = {
      name: i18n.t('fieldType.multipleSelectCheckboxes'),
      component: FormViewFieldMultipleSelectCheckboxes,
      properties: {},
    }

    return components
  }

  getCardComponent() {
    return RowCardFieldMultipleSelect
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldMultipleSelect
  }

  getSort(name, order) {
    return (a, b) => {
      const valuesA = a[name]
      const valuesB = b[name]
      const stringA =
        valuesA.length > 0 ? valuesA.map((obj) => obj.value).join(', ') : ''
      const stringB =
        valuesB.length > 0 ? valuesB.map((obj) => obj.value).join(', ') : ''

      return collatedStringCompare(stringA, stringB, order)
    }
  }

  prepareValueForUpdate(field, value) {
    if (value === undefined || value === null) {
      return []
    }
    return value.map((item) => item.id)
  }

  prepareValueForCopy(field, value) {
    if (value === undefined || value === null) {
      return ''
    }

    const nameList = value.map(({ value }) => value)
    // Use papa to generate a CSV string
    return this.app.$papa.arrayToString(nameList)
  }

  prepareRichValueForCopy(field, value) {
    if (value === undefined) {
      return []
    }
    return value
  }

  checkRichValueIsCompatible(value) {
    return (
      value === null ||
      (Array.isArray(value) &&
        value.every((v) => Object.prototype.hasOwnProperty.call(v, 'id')))
    )
  }

  /**
   Converts pasted options to select field options based on the fields existing select
   options. Matches by id first if that fails then by value. Ensures the produced
   select options are unique by id.
   */
  convertPastedOptionsToThisFields(existingSelectOptions, pastedDataArray) {
    const selectOptionNameMap = _.groupBy(existingSelectOptions, 'value')
    const selectOptionIdMap = _.keyBy(existingSelectOptions, 'id')
    const resultingSelectOptions = []

    pastedDataArray.forEach((pastedSelectOption) => {
      const existingSelectOptionWithSameId =
        selectOptionIdMap[pastedSelectOption?.id]
      if (existingSelectOptionWithSameId) {
        resultingSelectOptions.push(existingSelectOptionWithSameId)
      } else if (pastedSelectOption?.value) {
        const existingSelectOptionWithSameName =
          selectOptionNameMap[pastedSelectOption.value]?.shift()
        if (existingSelectOptionWithSameName) {
          resultingSelectOptions.push(existingSelectOptionWithSameName)
        }
      }
    })

    return _.uniqBy(resultingSelectOptions, 'id')
  }

  prepareValueForPaste(field, clipboardData, richClipboardData) {
    if (this.checkRichValueIsCompatible(richClipboardData)) {
      if (richClipboardData === null) {
        return []
      }
      return this.convertPastedOptionsToThisFields(
        field.select_options,
        richClipboardData
      )
    } else {
      // Fallback to text version
      try {
        const data = this.app.$papa
          .stringToArray(clipboardData)
          .map((value) => {
            return {
              value,
            }
          })
        return this.convertPastedOptionsToThisFields(field.select_options, data)
      } catch (e) {
        return []
      }
    }
  }

  toHumanReadableString(field, value, delimiter = ', ') {
    if (
      value === undefined ||
      value === null ||
      (Array.isArray(value) && value.length === 0)
    ) {
      return ''
    }
    return value.map((item) => item.value).join(delimiter)
  }

  getDocsDataType() {
    return 'array'
  }

  getDocsDescription(field) {
    const options = field.select_options
      .map(
        (option) =>
          // @TODO move this template to a component.
          `<div class="select-options-listing">
              <div class="select-options-listing__id">${option.id}</div>
              <div class="select-options-listing__value background-color--${option.color}">${option.value}</div>
           </div>
          `
      )
      .join('\n')

    return `
      ${this.app.i18n.t('fieldDocs.multipleSelect')}
      <br />
      ${options}
    `
  }

  getDocsRequestExample() {
    return [1]
  }

  getDocsResponseExample() {
    return [
      {
        id: 1,
        value: 'Option',
        color: 'light-blue',
      },
    ]
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  containsWordFilter(rowValue, filterValue, field) {
    return (
      filterValue === '' ||
      this.getContainsWordFilterFunction(field)(
        rowValue,
        this.toHumanReadableString(field, rowValue, ' '),
        filterValue
      )
    )
  }

  getContainsWordFilterFunction(field) {
    return genericContainsWordFilter
  }

  getEmptyValue(field) {
    return []
  }

  getDefaultValueFieldName() {
    return 'multiple_select_default'
  }

  getDefaultValue(field, flat) {
    const defaultValueFieldName = this.getDefaultValueFieldName()
    const defaultValue = field[defaultValueFieldName]
    if (defaultValue == null) {
      return this.getEmptyValue(field)
    }
    if (flat) {
      return defaultValue
    }
    return (defaultValue || [])
      .map((id) => field.select_options.find((opt) => opt.id === id))
      .filter(Boolean)
  }

  shouldFetchFieldSelectOptions() {
    return false
  }

  acceptSplitCommaSeparatedSelectOptions() {
    return true
  }

  canParseQueryParameter() {
    return true
  }

  /**
   * Accepts the following format: option1,option2,option3
   */
  parseQueryParameter(field, value) {
    const values = value.split(',')

    const selectOptions = field.field.select_options.filter((option) =>
      values.includes(option.value)
    )

    return selectOptions.length > 0 ? selectOptions : this.getDefaultValue()
  }

  getCanImport() {
    return true
  }

  canBeReferencedByFormulaField() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }

  getRowValueFromGroupValue(field, value) {
    return value.map((optId) => {
      return { id: optId }
    })
  }

  getGroupValueFromRowValue(field, value) {
    return value && value.map((o) => o.id)
  }

  isEqual(field, value1, value2) {
    const value1Ids = value1.map((v) => v.id)
    const value2Ids = value2.map((v) => v.id)

    return _.isEqual(value1Ids, value2Ids)
  }
}

export class PhoneNumberFieldType extends FieldType {
  static getType() {
    return 'phone_number'
  }

  static getIconClass() {
    return 'iconoir-phone'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.phoneNumber')
  }

  getGridViewFieldComponent() {
    return GridViewFieldPhoneNumber
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldURL
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldPhoneNumber
  }

  getCardComponent() {
    return RowCardFieldPhoneNumber
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldText
  }

  prepareValueForPaste(field, clipboardData) {
    const value = clipboardData
    return isSimplePhoneNumber(value) ? value : ''
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const stringA = a[name] === null ? '' : '' + a[name]
      const stringB = b[name] === null ? '' : '' + b[name]

      return collatedStringCompare(stringA, stringB, order)
    }
  }

  getDefaultValue(field, flat) {
    return ''
  }

  getValidationError(field, value) {
    if (value === null || value === '') {
      return null
    }
    if (!isSimplePhoneNumber(value)) {
      return this.app.i18n.t('fieldErrors.invalidPhoneNumber')
    }
    return null
  }

  getSortIndicator() {
    return ['text', '0', '9']
  }

  getDocsDataType(field) {
    return 'string'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.phoneNumber')
  }

  getDocsRequestExample(field) {
    return '+1-541-754-3010'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canParseQueryParameter() {
    return true
  }

  parseQueryParameter(field, value) {
    return value
  }

  getCanImport() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }
}

export class FormulaFieldType extends mix(
  formulaFieldArrayFilterMixin,
  FieldType
) {
  static getType() {
    return 'formula'
  }

  static getTypeAndSubTypes() {
    return [
      this.getType(),
      CountFieldType.getType(),
      RollupFieldType.getType(),
      LookupFieldType.getType(),
    ]
  }

  static compatibleWithFormulaTypes(...formulaTypeStrings) {
    return (field) => {
      return (
        this.getTypeAndSubTypes().includes(field.type) &&
        (formulaTypeStrings.includes(field.formula_type) ||
          (field.array_formula_type &&
            formulaTypeStrings.includes(
              this.arrayOf(field.array_formula_type)
            )))
      )
    }
  }

  static arrayOf(type) {
    return `array(${type})`
  }

  static getIconClass() {
    return 'baserow-icon-formula'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.formula')
  }

  parseFilterValue(field, value) {
    return this.getFormulaType(field)?.parseFilterValue(field, value)
  }

  formatFilterValue(field, value) {
    return this.getFormulaType(field)?.formatFilterValue(field, value)
  }

  getFormulaType(field) {
    return this.app.$registry.get('formula_type', field.formula_type)
  }

  getGridViewFieldComponent() {
    return GridViewFieldFormula
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldFormula
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldFormula
  }

  getCardComponent() {
    return RowCardFieldFormula
  }

  getFilterInputComponent(field, filterType) {
    return this.getFormulaType(field)?.getFilterInputComponent(
      field,
      filterType
    )
  }

  _mapFormulaTypeToFieldType(formulaType) {
    return this.app.$registry.get('formula_type', formulaType).getFieldType()
  }

  getCardValueHeight(field) {
    return this.getFormulaType(field)?.getCardComponent().height || 0
  }

  getCanSortInView(field) {
    return this.getFormulaType(field)?.getCanSortInView(field)
  }

  getSort(name, order, field) {
    return this.getFormulaType(field)?.getSort(name, order, field)
  }

  getSortTypes(field) {
    return this.getFormulaType(field)?.getSortTypes(field)
  }

  getDefaultValue(field, flat) {
    return null
  }

  getDocsDataType(field) {
    return this.getFormulaType(field)?.getDocsDataType(field)
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.formula')
  }

  getDocsRequestExample(field) {
    return 'it is invalid to include request data for this field as it is read only'
  }

  getDocsResponseExample(field) {
    return this.getFormulaType(field)?.getDocsResponseExample(field)
  }

  prepareValueForCopy(field, value) {
    return this.getFormulaType(field)?.prepareValueForCopy(field, value)
  }

  getContainsFilterFunction(field) {
    const underlyingFieldType = this.app.$registry.get(
      'field',
      this._mapFormulaTypeToFieldType(field.formula_type)
    )
    return underlyingFieldType.getContainsFilterFunction()
  }

  getContainsWordFilterFunction(field) {
    const underlyingFieldType = this.app.$registry.get(
      'field',
      this._mapFormulaTypeToFieldType(field.formula_type)
    )
    return underlyingFieldType.getContainsWordFilterFunction()
  }

  toHumanReadableString(field, value) {
    return this.getFormulaType(field)?.toHumanReadableString(field, value)
  }

  getSortIndicator(field) {
    return this.getFormulaType(field)?.getSortIndicator(field)
  }

  getFormComponent() {
    return FieldFormulaSubForm
  }

  /**
   * Can optionally return additional components that are rendered directly below
   * the field form formula input.
   */
  getAdditionalFormInputComponents() {
    return []
  }

  isReadOnlyField() {
    return true
  }

  shouldFetchDataWhenAdded() {
    return true
  }

  getFormViewFieldComponents(field) {
    return {}
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canRepresentDate(field) {
    return this.getFormulaType(field)?.canRepresentDate(field)
  }

  getCanGroupByInView(field) {
    return this.getFormulaType(field)?.canGroupByInView(field)
  }

  isEqual(field, value1, value2) {
    return this.getFormulaType(field).isEqual(field, value1, value2)
  }

  getRowValueFromGroupValue(field, value) {
    return this.getFormulaType(field).getRowValueFromGroupValue(field, value)
  }

  getGroupValueFromRowValue(field, value) {
    return this.getFormulaType(field).getGroupValueFromRowValue(field, value)
  }

  parseInputValue(field, value) {
    return this.getFormulaType(field).parseInputValue(field, value)
  }

  parseFromLinkedRowItemValue(field, value) {
    return this.getFormulaType(field).parseFromLinkedRowItemValue(field, value)
  }

  canRepresentFiles(field) {
    return this.getFormulaType(field)?.canRepresentFiles(field)
  }

  toBaserowFormulaType(field) {
    return this.getFormulaType(field).toBaserowFormulaType(field)
  }

  canHaveDbIndex(fieldValues) {
    // Not all the formula types are compatible with the indexes, but the downside
    // is that the frontend only knows the new formula type after saving, so it's
    // impossible to preemptively know if indexes are supported. We're therefore
    // always allowing indexes, and if the formula type is not compatible, the
    // backend will fail, and will show the correct error in the form.
    return true
  }
}

export class CountFieldType extends FormulaFieldType {
  static getType() {
    return 'count'
  }

  static getIconClass() {
    return 'iconoir-calculator'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.count')
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.count')
  }

  getFormComponent() {
    return FieldCountSubForm
  }

  shouldFetchFieldSelectOptions() {
    return false
  }
}

export class RollupFieldType extends FormulaFieldType {
  static getType() {
    return 'rollup'
  }

  static getIconClass() {
    return 'iconoir-box-iso'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.rollup')
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.rollup')
  }

  getFormComponent() {
    return FieldRollupSubForm
  }

  shouldFetchFieldSelectOptions() {
    return false
  }
}

export class LookupFieldType extends FormulaFieldType {
  static getType() {
    return 'lookup'
  }

  static getIconClass() {
    return 'iconoir-binocular'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.lookup')
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.lookup')
  }

  getFormComponent() {
    return FieldLookupSubForm
  }

  shouldFetchFieldSelectOptions() {
    return false
  }
}

export class MultipleCollaboratorsFieldType extends FieldType {
  static getType() {
    return 'multiple_collaborators'
  }

  static getIconClass() {
    return 'iconoir-community'
  }

  parseFromLinkedRowItemValue(field, value) {
    return this.app.store.getters['workspace/getUserByEmail'](value) || null
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.multipleCollaborators')
  }

  getAlias() {
    return 'people person team'
  }

  getFormComponent() {
    return FieldCollaboratorSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldMultipleCollaborators
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldMultipleCollaborators
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldMultipleCollaborators
  }

  getCardComponent() {
    return RowCardFieldMultipleCollaborators
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldMultipleCollaborators
  }

  prepareValueForUpdate(field, value) {
    if (value === undefined || value === null) {
      return []
    }
    return value
  }

  getFormViewFieldComponents(field) {
    const { i18n } = this.app
    const components = super.getFormViewFieldComponents(field)
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].name = i18n.t(
      'fieldType.multipleCollaboratorsDropdown'
    )
    components[DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY].properties = {
      'allow-create-options': false,
    }
    components.checkboxes = {
      name: i18n.t('fieldType.multipleCollaboratorsCheckboxes'),
      component: FormViewFieldMultipleCollaboratorsCheckboxes,
      properties: {},
    }
    return components
  }

  getDefaultValue(field, flat) {
    return []
  }

  getCanImport() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const valuesA = a[name]
      const valuesB = b[name]

      let stringA = ''
      let stringB = ''

      const workspaces = this.app.store.getters['workspace/getAll']

      if (valuesA.length > 0 && workspaces.length > 0) {
        stringA = valuesA
          .map(
            (obj) =>
              this.app.store.getters['workspace/getUserById'](obj.id).name
          )
          .join('')
      } else if (valuesA.length > 0) {
        stringA = valuesA.map((obj) => obj.name).join('')
      }

      if (valuesB.length > 0 && workspaces.length > 0) {
        stringB = valuesB
          .map(
            (obj) =>
              this.app.store.getters['workspace/getUserById'](obj.id).name
          )
          .join('')
      } else if (valuesB.length > 0) {
        stringB = valuesB.map((obj) => obj.name).join('')
      }

      return collatedStringCompare(stringA, stringB, order)
    }
  }

  prepareValueForCopy(field, value) {
    if (value === undefined || value === null) {
      return ''
    }
    const nameList = this._collaboratorCellValueToListOfNames(value)

    return this.app.$papa.unparse([nameList], { delimiter: ', ' })
  }

  _collaboratorCellValueToListOfNames(value) {
    const workspaces = this.app.store.getters['workspace/getAll']

    if (workspaces.length > 0) {
      return value.map((value) => {
        const workspaceUser = this.app.store.getters['workspace/getUserById'](
          value.id
        )
        return workspaceUser.name
      })
    } else {
      // public views
      return value.map((value) => {
        return value.name
      })
    }
  }

  prepareRichValueForCopy(field, value) {
    if (value === undefined) {
      return []
    }
    return value
  }

  checkRichValueIsCompatible(value) {
    return (
      value === null ||
      (Array.isArray(value) &&
        value.every((v) => Object.prototype.hasOwnProperty.call(v, 'id')))
    )
  }

  prepareValueForPaste(field, clipboardData, richClipboardData) {
    if (this.checkRichValueIsCompatible(richClipboardData)) {
      if (richClipboardData === null) {
        return []
      }
      return richClipboardData
    } else {
      // Fallback to text version
      try {
        const data = this.app.$papa.stringToArray(clipboardData)
        const uniqueValuesOnly = Array.from(new Set(data))

        return uniqueValuesOnly
          .map((emailOrName) => {
            // verify if it respects the format `$name ($email)`
            const matches = emailOrName.match(/(.*)\s*<(.*)>/)
            let email = emailOrName
            if (matches) {
              email = matches[2]
            }
            const workspaceUser =
              this.app.store.getters['workspace/getUserByEmail'](email)
            if (workspaceUser !== undefined) {
              return workspaceUser
            }
            return this.app.store.getters['workspace/getUserByName'](
              emailOrName
            )
          })
          .filter((obj) => obj !== null)
          .map((obj) => {
            return {
              id: obj.user_id,
              name: obj.name,
            }
          })
      } catch (e) {
        return []
      }
    }
  }

  getDocsDataType() {
    return 'array'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.multipleCollaborators')
  }

  getDocsRequestExample() {
    return [{ id: 1 }]
  }

  getDocsResponseExample() {
    return [
      {
        id: 1,
        name: 'John',
      },
    ]
  }

  toHumanReadableString(field, value, delimiter = ', ') {
    if (value === undefined || value === null) {
      return ''
    }
    return this._collaboratorCellValueToListOfNames(value).join(delimiter)
  }

  canBeReferencedByFormulaField() {
    return true
  }

  getCanGroupByInView(field) {
    return true
  }

  getRowValueFromGroupValue(field, value) {
    return value.map((optId) => {
      return { id: optId }
    })
  }

  getGroupValueFromRowValue(field, value) {
    return value && value.map((o) => o.id)
  }

  isEqual(field, value1, value2) {
    const value1Ids = value1.map((v) => v.id)
    const value2Ids = value2.map((v) => v.id)

    return _.isEqual(value1Ids, value2Ids)
  }
}

export class UUIDFieldType extends FieldType {
  static getType() {
    return 'uuid'
  }

  static getIconClass() {
    return 'iconoir-fingerprint'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.uuid')
  }

  getFormViewFieldComponents(field) {
    return {}
  }

  isReadOnlyField() {
    return true
  }

  shouldFetchDataWhenAdded() {
    return true
  }

  getGridViewFieldComponent() {
    return GridViewFieldUUID
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldUUID
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldUUID
  }

  getCardComponent() {
    return RowCardFieldUUID
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      const stringA = a[name] === null ? '' : '' + a[name]
      const stringB = b[name] === null ? '' : '' + b[name]
      return collatedStringCompare(stringA, stringB, order)
    }
  }

  getDocsDataType(field) {
    return 'uuid'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.uuid')
  }

  getDocsRequestExample(field) {
    return '00000000-0000-0000-0000-000000000000'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  getContainsWordFilterFunction(field) {
    return genericContainsWordFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canHaveDbIndex(fieldValues) {
    return true
  }
}

export class AutonumberFieldType extends FieldType {
  static getType() {
    return 'autonumber'
  }

  static getIconClass() {
    return 'iconoir-numbered-list-left'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.autonumber')
  }

  getFormViewFieldComponents(field) {
    return {}
  }

  isReadOnlyField() {
    return true
  }

  shouldFetchDataWhenAdded() {
    return true
  }

  getGridViewFieldComponent() {
    return GridViewFieldAutonumber
  }

  getFormComponent() {
    return FieldAutonumberSubForm
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridViewFieldAutonumber
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldAutonumber
  }

  getCardComponent() {
    return RowCardFieldAutonumber
  }

  canUpsert() {
    return true
  }

  getSort(name, order) {
    return (a, b) => {
      if (a[name] === b[name]) {
        return 0
      }

      if (
        (a[name] === null && order === 'ASC') ||
        (b[name] === null && order === 'DESC')
      ) {
        return -1
      }

      if (
        (b[name] === null && order === 'ASC') ||
        (a[name] === null && order === 'DESC')
      ) {
        return 1
      }

      const numberA = new BigNumber(a[name])
      const numberB = new BigNumber(b[name])

      let result
      // Add your code here

      if (order === 'ASC') {
        result = numberA.isLessThan(numberB) ? -1 : 1
      } else {
        result = numberB.isLessThan(numberA) ? -1 : 1
      }

      return result
    }
  }

  getDocsDataType(field) {
    return 'autonumber'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.autonumber')
  }

  getDocsRequestExample(field) {
    return '1'
  }

  getContainsFilterFunction() {
    return genericContainsFilter
  }

  canBeReferencedByFormulaField() {
    return true
  }

  canHaveDbIndex(fieldValues) {
    return true
  }
}

export class PasswordFieldType extends FieldType {
  static getType() {
    return 'password'
  }

  static getIconClass() {
    return 'iconoir-lock'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('fieldType.password')
  }

  getFormComponent() {
    return FieldPasswordSubForm
  }

  getGridViewFieldComponent() {
    return GridViewFieldPassword
  }

  getFunctionalGridViewFieldComponent() {
    return FunctionalGridVIewFieldPassword
  }

  getRowEditFieldComponent(field) {
    return RowEditFieldPassword
  }

  getCardComponent() {
    return RowCardFieldPassword
  }

  getDocsDataType(field) {
    return 'boolean'
  }

  getDocsDescription(field) {
    return this.app.i18n.t('fieldDocs.password')
  }

  getDocsRequestExample(field) {
    return 'true'
  }

  getCanSortInView(field) {
    return false
  }

  getValidationError(field, value) {
    if (value === null) {
      return null
    }

    const stringValue = value.toString()
    if (stringValue.length < 1) {
      return this.app.i18n.t('fieldErrors.minChars', { min: 1 })
    }
    if (stringValue.length > 128) {
      return this.app.i18n.t('fieldErrors.maxChars', { max: 128 })
    }
    return null
  }

  prepareValueForCopy(field, value) {
    return ''
  }

  getCanBePrimaryField() {
    return false
  }

  toHumanReadableString(field, value, delimiter = ', ') {
    return value ? '••••••••••' : ''
  }

  getRowHistoryEntryComponent() {
    return RowHistoryFieldPassword
  }
}
