import { Registerable } from '@baserow/modules/core/registry'

export default class TimelineFieldRuleType extends Registerable {
  /**
   * Returns field rule type name that is associated with this TimelineFieldRuleType
   *
   * @returns {string}
   */
  getType() {}

  /**
   * Returns a component that will be used to render a field rule for a single row
   */
  getTimelineFieldRuleComponent(rule, view, database) {}
}
