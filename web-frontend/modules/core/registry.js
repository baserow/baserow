/**
 * Only instances that are children of a Registerable can be registered into the
 * registry.
 */
export class Registerable {
  constructor({ app } = {}) {
    this.app = app
  }

  /**
   * Must return a string with the unique name, this must be the same as the
   * type used in the backend.
   */
  static getType() {
    throw new Error('The type of a registry must be set.')
  }

  getType() {
    return this.constructor.getType()
  }

  get type() {
    return this.constructor.getType()
  }

  set type(newType) {
    // Does nothing as the type shouldn't be modifiable
  }

  /**
   * Returns a weight to order the registerable. Used when you want an ordered list
   * of all registered items.
   * @returns order weight. Lower value first in the list.
   */
  getOrder() {
    return 0
  }

  $t(key) {
    const { i18n } = this.app
    return i18n.t(key)
  }
}

/**
 * The registry is an class where Registerable instances can be registered under a
 * namespace. This is used for plugins to register extra functionality to Baserow. For
 * example the database plugin registers itself as an application to the core, but
 * it is also possible to register fields and views to the database plugin.
 */
export class Registry {
  constructor() {
    this.registry = {}
  }

  /**
   * Registers an empty namespace.
   */
  registerNamespace(namespace) {
    this.registry[namespace] = {}
  }

  /**
   * Registers a new Registerable object under the provided namespace in the registry.
   * If the namespace doesn't exist it will be created. It is common to register
   * instantiated classes here.
   */
  register(namespace, object) {
    if (!(object instanceof Registerable)) {
      throw new TypeError(
        'The registered object must be an instance of Registrable.'
      )
    }
    const type = object.getType()

    if (!Object.prototype.hasOwnProperty.call(this.registry, namespace)) {
      this.registry[namespace] = {}
    }
    this.registry[namespace][type] = object
  }

  /**
   * Un-registers a registered type from the provided namespace in the
   * registry. Throws an error if the registry does not exist. Returns true if the
   * type was found and deleted successfully, or false if the type did not exist in
   * the namespace.
   */
  unregister(namespace, type) {
    if (!Object.prototype.hasOwnProperty.call(this.registry, namespace)) {
      throw new Error(
        `The namespace ${namespace} is not found in the registry.`
      )
    }
    return delete this.registry[namespace][type]
  }

  /**
   * Returns a registered object with the given type in the provided namespace.
   */
  get(namespace, type) {
    if (!Object.prototype.hasOwnProperty.call(this.registry, namespace)) {
      throw new Error(
        `The namespace ${namespace} is not found in the registry.`
      )
    }
    if (!Object.prototype.hasOwnProperty.call(this.registry[namespace], type)) {
      throw new Error(
        `The type "${type}" is not found under namespace "${namespace}" in the registry.`
      )
    }
    return this.registry[namespace][type]
  }

  /**
   * Returns all the objects that are in the given namespace.
   */
  getAll(namespace) {
    if (!Object.prototype.hasOwnProperty.call(this.registry, namespace)) {
      throw new Error(
        `The namespace ${namespace} is not found in the registry.`
      )
    }
    return this.registry[namespace]
  }

  /** Returns an array of the types */
  getList(namespace) {
    return Object.values(this.getAll(namespace))
  }

  /**
   * Returns a list of the objects that are in the given namespace ordered by their
   * `.getOrder()` value. Lower value first then for equality, the insertion order is
   * considered.
   */
  getOrderedList(namespace) {
    return Object.values(this.getAll(namespace)).sort(
      (typeA, typeB) => typeA.getOrder() - typeB.getOrder()
    )
  }

  /**
   * Returns true if the object of the given type exists in the namespace.
   */
  exists(namespace, type) {
    if (!Object.prototype.hasOwnProperty.call(this.registry, namespace)) {
      return false
    }
    if (!Object.prototype.hasOwnProperty.call(this.registry[namespace], type)) {
      return false
    }
    return true
  }

  /**
   * Returns the specific constraint for the field type and constraint type name.
   *
   * @param {string} namespace - The registry namespace (e.g., 'fieldConstraint')
   * @param {string} constraintTypeName - The type name of the constraint
   * @param {string} fieldType - The field type to check compatibility with
   * @returns {Registerable|null} The specific constraint or null if no compatible constraint is found
   */
  getSpecificConstraint(namespace, constraintTypeName, fieldType) {
    if (!Object.prototype.hasOwnProperty.call(this.registry, namespace)) {
      return null
    }

    for (const constraint of Object.values(this.registry[namespace])) {
      if (
        constraint.getTypeName() === constraintTypeName &&
        constraint.getCompatibleFieldTypes().includes(fieldType)
      ) {
        return constraint
      }
    }
    return null
  }
}
