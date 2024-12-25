/**
 * Supporting JS module to define and use plain
 * JavaScript mixins.
 */

/**
 * The mix function can be used to extend a class with mixin
 * objects that provide common behavior.
 *
 * In case that the class define a function that exists in the
 * mixin, the class implementation will take precedence over
 * the function in the mixin.
 *
 * Typical usage:
 *
 * const canFlyMixin = {
 *    fly() {
 *      ...
 *    }
 *  }
 *
 *  const canSwimMixin = {
 *    swim() {
 *      ...
 *    }
 *  }
 *
 *  class Animal {
 *    constructor(name) {
 *      this.name = name;
 *    }
 *  }
 *
 *  class Duck extends mix(canFlyMixin, canSwimMixin, Animal) {}
 */
export function mix(...chain) {
  const [baseClass, ...mixins] = chain.reverse()

  class Mixed extends baseClass {}

  for (const mixin of mixins) {
    for (const [key, value] of Object.entries(mixin)) {
      /* eslint no-prototype-builtins: "off" */
      if (!Mixed.prototype.hasOwnProperty(key)) {
        Mixed.prototype[key] = value
      }
    }
  }

  return Mixed
}
