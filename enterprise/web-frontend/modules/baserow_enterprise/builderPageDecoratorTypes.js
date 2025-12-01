import { Registerable } from '@baserow/modules/core/registry'
import EnterpriseFeaturesObject from '@baserow_enterprise/features'

/**
 * The BuilderPageDecorator type serves as a wrapper component that can be
 * registered and applied around page content in published builder apps.
 */
export class BuilderPageDecoratorType extends Registerable {
  /**
   * Must return a string containing the type of the decorator.
   */
  static getType() {
    throw new Error('Must be set by the implementing subclass.')
  }

  /**
   * Component that will be rendered to wrap the page content.
   * The component must use a slot to render the wrapped content.
   */
  get component() {
    throw new Error('Must be set by the implementing subclass')
  }

  /**
   * Returns whether the decorator should be applied for the current context.
   * This is called to determine if the decorator should be applied to the page.
   */
  isDecorationAllowed(workspace = {}) {
    return true
  }

  /**
   * Should return an object with props to pass to the component.
   */
  getProps() {
    return {}
  }
}

/**
 * A decorator that adds a "Made with Baserow" badge to the bottom right
 * of published builder pages when the workspace doesn't have an
 * Enterprise/Advanced license.
 */
export class MadeWithBaserowBuilderPageDecoratorType extends BuilderPageDecoratorType {
  static getType() {
    return 'made_with_baserow'
  }

  get component() {
    return require('@baserow_enterprise/components/builder/MadeWithBaserowBuilderDecorator')
      .default
  }

  isDecorationAllowed(workspace) {
    return !this.app.$hasFeature(
      EnterpriseFeaturesObject.BUILDER_NO_BRANDING,
      workspace.id
    )
  }
}
