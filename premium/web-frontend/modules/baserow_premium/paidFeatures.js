import { Registerable } from '@baserow/modules/core/registry'

export class PaidFeature extends Registerable {
  getPlan() {
    throw new Error('The `getPlan` method must be added to the paid feature.')
  }

  getName() {
    throw new Error('The `getName` method must be added to the paid feature.')
  }

  getIconClass() {
    throw new Error(
      'The `getIconClass` method must be added to the paid feature.'
    )
  }

  getImage() {
    return null
  }

  getContent() {
    return ''
  }
}

export class KanbanViewPaidFeature extends PaidFeature {
  static getType() {
    return 'kanban_view'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'baserow-icon-kanban'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.kanbanView')
  }

  getImage() {
    return '/img/features/kanban_view.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.kanbanViewContent')
  }
}

export class CalendarViewPaidFeature extends PaidFeature {
  static getType() {
    return 'calendar_view'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'baserow-icon-calendar'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.calendarView')
  }

  getImage() {
    return '/img/features/calendar_view.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.calendarViewContent')
  }
}

export class TimelineViewPaidFeature extends PaidFeature {
  static getType() {
    return 'timeline_view'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'baserow-icon-timeline'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.timelineView')
  }

  getImage() {
    return '/img/features/timeline_view.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.timelineViewContent')
  }
}

export class RowColoringPaidFeature extends PaidFeature {
  static getType() {
    return 'row_coloring'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-palette'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.rowColoring')
  }

  getImage() {
    return '/img/features/row_coloring.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.rowColoringContent')
  }
}

export class RowCommentsPaidFeature extends PaidFeature {
  static getType() {
    return 'row_comments'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-multi-bubble'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.rowComments')
  }

  getImage() {
    return '/img/features/row_comments.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.rowCommentsContent')
  }
}

export class RowNotificationsPaidFeature extends PaidFeature {
  static getType() {
    return 'row_notifications'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-bell'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.rowNotifications')
  }

  getImage() {
    return '/img/features/row_notifications.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.rowNotificationsContent')
  }
}

export class AIPaidFeature extends PaidFeature {
  static getType() {
    return 'ai_features'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-magic-wand'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.aiFeatures')
  }

  getImage() {
    return '/img/features/ai_features.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.aiFeaturesContent')
  }
}

export class PersonalViewsPaidFeature extends PaidFeature {
  static getType() {
    return 'personal_views'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-lock'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.personalViews')
  }

  getImage() {
    return '/img/features/personal_views.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.personalViewsContent')
  }
}

export class ExportsPaidFeature extends PaidFeature {
  static getType() {
    return 'exports'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-database-export'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.exports')
  }

  getImage() {
    return '/img/features/table_exports.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.exportsContent')
  }
}

export class PublicLogoRemovalPaidFeature extends PaidFeature {
  static getType() {
    return 'public_logo_removal'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-eye-close'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.publicLogoRemoval')
  }

  getImage() {
    return '/img/features/public_view_logo_removal.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.publicLogoRemovalContent')
  }
}

export class FormSurveyModePaidFeature extends PaidFeature {
  static getType() {
    return 'form_survey_mode'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-reports'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.surveyForm')
  }

  getImage() {
    return '/img/features/survey_form.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.surveyFormContent')
  }
}

export class ChartPaidFeature extends PaidFeature {
  static getType() {
    return 'chart'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'baserow-icon-dashboard'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.chartWidget')
  }

  getImage() {
    return '/img/features/chart_widget.png'
  }

  getContent() {
    return this.app.i18n.t('premiumFeatures.chartWidgetContent')
  }
}
