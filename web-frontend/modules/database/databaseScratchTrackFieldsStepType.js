import moment from '@baserow/modules/core/moment'
import {
  BooleanFieldType,
  DateFieldType,
  DurationFieldType,
  EmailFieldType,
  LongTextFieldType,
  NumberFieldType,
  PhoneNumberFieldType,
  RatingFieldType,
  SingleSelectFieldType,
  URLFieldType,
} from '@baserow/modules/database/fieldTypes'
import { Registerable } from '@baserow/modules/core/registry'

export const fieldHandlerRegistry = {
  [SingleSelectFieldType.getType()]: function (field, response) {
    return response.data.select_options.map((option) => option.id)
  },
}

export class DatabaseScratchTrackFieldsOnboardingType extends Registerable {
  static getType() {
    return 'database_scratch_track'
  }

  getField(name, fieldType, fieldProps, rows) {
    const trKey = name.charAt(0).toUpperCase() + name.slice(1)
    const trName = this.$t(`databaseScratchTrackFieldsStep.field${trKey}`)
    return {
      name: trName,
      props: {
        name: trName,
        type: fieldType.getType(),
        ...fieldProps,
      },
      icon: fieldType.getIconClass(),
      rows,
    }
  }

  getOwnFields() {
    return [
      this.getField('description', LongTextFieldType, {}, [
        this.$t('databaseScratchTrackFieldsStep.customFieldsDescriptionRow1'),
        this.$t('databaseScratchTrackFieldsStep.customFieldsDescriptionRow2'),
        this.$t('databaseScratchTrackFieldsStep.customFieldsDescriptionRow3'),
      ]),
      this.getField(
        'number',
        NumberFieldType,
        { number_decimal_places: 2, number_negative: true },
        [0, -500, 131.35]
      ),
      this.getField('date', DateFieldType, { date_format: 'ISO' }, [
        moment().subtract(3, 'months').format('YYYY-MM-DD'),
        moment().add(1, 'days').format('YYYY-MM-DD'),
        moment().add(1, 'months').format('YYYY-MM-DD'),
      ]),
      this.getField('boolean', BooleanFieldType, {}, [true, false, true]),
      this.getField(
        'duration',
        DurationFieldType,
        { duration_format: 'h:mm:ss' },
        [100, 1000, 10000]
      ),
      this.getField('url', URLFieldType, {}, [
        'https://tcrprojects.com',
        'https://example.com',
        'https://gitlab.com/tcrprojects',
      ]),
      this.getField('email', EmailFieldType, {}, [
        'donnmoore@company.com',
        'gordonb@company.com',
        'janetcook@company.com',
      ]),
      this.getField('rating', RatingFieldType, { max_value: 5 }, [3, 1, 5]),
    ]
  }

  getFields() {
    return {}
  }

  afterFieldCreated(field, response) {
    const fieldHandler = fieldHandlerRegistry[field.props.type]
    if (fieldHandler) {
      field.rows = fieldHandler(field, response)
    }
  }
}

export class DatabaseScratchTrackProjectFieldsOnboardingType extends DatabaseScratchTrackFieldsOnboardingType {
  static getType() {
    return 'database_scratch_track_fields_projects'
  }

  getFields() {
    const selectOptions = [
      {
        id: -1,
        value: this.$t('databaseScratchTrackFieldsStep.projectsCategoryDesign'),
        color: 'gray',
      },
      {
        id: -2,
        value: this.$t(
          'databaseScratchTrackFieldsStep.projectsCategoryDevelopment'
        ),
        color: 'yellow',
      },
      {
        id: -3,
        value: this.$t(
          'databaseScratchTrackFieldsStep.projectsCategoryMarketing'
        ),
        color: 'blue',
      },
    ]

    return {
      category: this.getField(
        'category',
        SingleSelectFieldType,
        { select_options: selectOptions },
        selectOptions
      ),

      kickoffDate: this.getField(
        'kickoffDate',
        DateFieldType,
        { date_format: 'ISO' },
        [
          moment().subtract(1, 'months').format('YYYY-MM-DD'),
          moment().add(1, 'weeks').format('YYYY-MM-DD'),
          moment().add(1, 'months').format('YYYY-MM-DD'),
        ]
      ),
      dueDate: this.getField('dueDate', DateFieldType, { date_format: 'ISO' }, [
        moment().subtract(1, 'months').format('YYYY-MM-DD'),
        moment().add(1, 'days').format('YYYY-MM-DD'),
        moment().add(3, 'weeks').format('YYYY-MM-DD'),
      ]),
      budget: this.getField(
        'budget',
        NumberFieldType,
        {
          number_decimal_places: 0,
          number_negative: false,
        },
        [500, 1000, 3000]
      ),
      completed: this.getField('completed', BooleanFieldType, {}, [
        true,
        false,
        false,
      ]),
      notes: this.getField('notes', LongTextFieldType, {}, [
        this.$t('databaseScratchTrackFieldsStep.projectsNotesRow1'),
        this.$t('databaseScratchTrackFieldsStep.projectsNotesRow2'),
        this.$t('databaseScratchTrackFieldsStep.projectsNotesRow3'),
      ]),
    }
  }
}

export class DatabaseScratchTrackTeamFieldsOnboardingType extends DatabaseScratchTrackFieldsOnboardingType {
  static getType() {
    return 'database_scratch_track_fields_teams'
  }

  getFields() {
    const selectOptions = [
      {
        id: 1,
        value: this.$t('databaseScratchTrackFieldsStep.teamsRoleDesigner'),
        color: 'gray',
      },
      {
        id: 2,
        value: this.$t('databaseScratchTrackFieldsStep.teamsRoleDeveloper'),
        color: 'yellow',
      },
      {
        id: 3,
        value: this.$t('databaseScratchTrackFieldsStep.teamsRoleMarketer'),
        color: 'blue',
      },
    ]
    return {
      role: this.getField(
        'role',
        SingleSelectFieldType,
        { select_options: selectOptions },
        selectOptions
      ),

      phone: this.getField('phone', PhoneNumberFieldType, {}, [
        '(508) 398-0845',
        '(803) 996-6704',
        '(269) 445-2068',
      ]),
      email: this.getField('email', EmailFieldType, {}, [
        'donnmoore@company.com',
        'gordonb@company.com',
        'janetcook@company.com',
      ]),
      active: this.getField('active', BooleanFieldType, {}, [
        true,
        false,
        true,
      ]),
    }
  }
}

export class DatabaseScratchTrackTaskFieldsOnboardingType extends DatabaseScratchTrackFieldsOnboardingType {
  static getType() {
    return 'database_scratch_track_fields_tasks'
  }

  getFields() {
    return {
      estimatedDays: this.getField(
        'estimatedDays',
        NumberFieldType,
        {
          number_decimal_places: 0,
          number_negative: false,
        },
        [2, 7, 13]
      ),
      completed: this.getField('completed', BooleanFieldType, {}, [
        true,
        false,
        false,
      ]),
      description: this.getField('details', LongTextFieldType, {}, [
        this.$t('databaseScratchTrackFieldsStep.tasksDetailsRow1'),
        this.$t('databaseScratchTrackFieldsStep.tasksDetailsRow2'),
        this.$t('databaseScratchTrackFieldsStep.tasksDetailsRow3'),
      ]),
    }
  }
}

export class DatabaseScratchTrackCampaignFieldsOnboardingType extends DatabaseScratchTrackFieldsOnboardingType {
  static getType() {
    return 'database_scratch_track_fields_campaigns'
  }

  getFields() {
    return {
      description: this.getField('details', LongTextFieldType, {}, [
        this.$t('databaseScratchTrackFieldsStep.campaignsDetailsRow1'),
        this.$t('databaseScratchTrackFieldsStep.campaignsDetailsRow2'),
        this.$t('databaseScratchTrackFieldsStep.campaignsDetailsRow3'),
      ]),
      startDate: this.getField(
        'startDate',
        DateFieldType,
        { date_format: 'ISO' },
        [
          moment().subtract(1, 'months').format('YYYY-MM-DD'),
          moment().add(1, 'weeks').format('YYYY-MM-DD'),
          moment().add(1, 'months').format('YYYY-MM-DD'),
        ]
      ),
      endDate: this.getField('endDate', DateFieldType, { date_format: 'ISO' }, [
        moment().subtract(1, 'months').format('YYYY-MM-DD'),
        moment().add(1, 'days').format('YYYY-MM-DD'),
        moment().add(3, 'weeks').format('YYYY-MM-DD'),
      ]),
      budget: this.getField(
        'budget',
        NumberFieldType,
        { number_decimal_places: 2, number_negative: false },
        [12000, 30000, 2000]
      ),
    }
  }
}

export class DatabaseScratchTrackCustomFieldsOnboardingType extends DatabaseScratchTrackFieldsOnboardingType {
  static getType() {
    return 'database_scratch_track_fields_custom'
  }

  getFields() {
    return {
      date: this.getField('date', DateFieldType, { date_format: 'ISO' }, [
        moment().subtract(1, 'months').format('YYYY-MM-DD'),
        moment().add(1, 'weeks').format('YYYY-MM-DD'),
        moment().add(1, 'months').format('YYYY-MM-DD'),
      ]),
      number: this.getField(
        'number',
        NumberFieldType,
        { number_decimal_places: 0, number_negative: true },
        [500, -1000, 3000]
      ),
      completed: this.getField('completed', BooleanFieldType, {}, [
        true,
        false,
        false,
      ]),
      description: this.getField('description', LongTextFieldType, {}, [
        this.$t('databaseScratchTrackFieldsStep.customFieldsDescriptionRow1'),
        this.$t('databaseScratchTrackFieldsStep.customFieldsDescriptionRow2'),
        this.$t('databaseScratchTrackFieldsStep.customFieldsDescriptionRow3'),
      ]),
    }
  }
}
