import _ from 'lodash'
import Vue from 'vue'

/**
 * Clones the provided JavaScript object and returns that one.
 *
 * @param o
 * @return {object}
 */
export function clone(o) {
  return JSON.parse(JSON.stringify(o))
}

/**
 * Checks if target object is a subset of source object
 * All keys in target must exist in source with matching values
 * Uses _.isEqual for deep comparison.
 */
export function isSubObject(source, target) {
  // Handle null/undefined cases
  if (target == null) return true
  if (source == null) return false

  // Check each key-value pair in target
  for (const key in target) {
    if (!Object.prototype.hasOwnProperty.call(target, key)) continue

    // If key doesn't exist in source, it's not a match
    if (!Object.prototype.hasOwnProperty.call(source, key)) {
      return false
    }

    // Use lodash isEqual for deep comparison
    if (!_.isEqual(source[key], target[key])) {
      return false
    }
  }

  return true
}

/**
 * Creates an object where the key indicates the line number and the value is
 * the string that must be shown on that line number. The line number matches
 * the line number if the value would be stringified with an indent of 4
 * characters `JSON.stringify(value, null, 4)`. The correct value is matched
 * if a value (recursive) object key matches a key of the mapping. However values will
 * not be matched inside the children of a matching key.
 *
 * Example:
 * mappingToStringifiedJSONLines(
 *  { key_2: 'Value' },
 *  {
 *    key_1: 'A random value',
 *    key_2: 'Another value'
 *  }
 * ) === {
 *   3: 'Value'
 * }
 */
export function mappingToStringifiedJSONLines(
  mapping,
  value,
  index = 1,
  lines = {},
  first = true
) {
  if (Array.isArray(value)) {
    index += 1
    value.forEach((v, i) => {
      index = mappingToStringifiedJSONLines(mapping, v, index, lines, false)
    })
    index += 1
    return first ? lines : index
  } else if (value instanceof Object) {
    index += 1
    Object.keys(value).forEach((k) => {
      let childMapping = mapping
      if (Object.prototype.hasOwnProperty.call(mapping, k)) {
        lines[index] = mapping[k]
        // Only recursively search for more field to line mappings where the current key
        // is not itself the key for a field.
        // For example if this key is a field, then there cannot be any other fields
        // to map within this fields value.
        childMapping = {}
      }
      index = mappingToStringifiedJSONLines(
        childMapping,
        value[k],
        index,
        lines,
        false
      )
    })
    index += 1
    return first ? lines : index
  } else {
    index += 1
    return first ? lines : index
  }
}

export function isPromise(p) {
  return (
    p !== null &&
    typeof p === 'object' &&
    typeof p.then === 'function' &&
    typeof p.catch === 'function'
  )
}

/**
 * Get the value at `path` of `obj`, similar to Lodash `get` function.
 *
 * @param {Object} obj The object that holds the value
 * @param {string | Array[string]} path The path to the value or a list with the path parts
 * @param {any} defaultValue The value to return if the path is not found
 * @return {Object} The value held by the path
 */
export function getValueAtPath(context, path) {
  function _getValueAtPath(obj, keys) {
    const [first, ...rest] = keys
    if (first === undefined || first === null) {
      return obj
    }

    if (obj === null || obj === undefined) {
      throw new Error(`Path '${path}' not found in context '${obj}'`)
    }

    if (first in obj) {
      return _getValueAtPath(obj[first], rest)
    }
    if (Array.isArray(obj) && first === '*') {
      const results = obj
        // Call recursively this function transforming the `*` in the path in a list
        // of indexes present in the object, e.g:
        // get(obj, "a.*.b") <=> [get(obj, "a.0.b"), get(obj, "a.1.b"), ...]
        .map((_, index) => _getValueAtPath(obj, [index.toString(), ...rest]))
        // Remove empty results
        // Note: Don't exclude false values such as booleans, empty strings, etc.
        .filter((result) => result !== null && result !== undefined)
      // Return null in case there are no results
      return results.length ? results : null
    }
    return null
  }
  const keys = typeof path === 'string' ? _.toPath(path) : path
  return _getValueAtPath(context, keys)
}

/**
 * Deeply sets a value in an object (or array) from a dotted path string.
 * Creates any missing intermediate parts if necessary.
 * Use Vue.set to keep reactivity.
 *
 * @param {Object} obj - The object we want to update.
 * @param {String} path - The path, delimited by periods, to the value.
 * @param {Any} value - The value to set at the path.
 */
export function setValueAtPath(obj, path, value) {
  // Note: We can't use `_.set` or `_.setWith` because would update all intermediary
  // level and that's not what we want.
  const keys = path.split('.')
  let current = obj

  for (let i = 0; i < keys.length; i++) {
    const key = keys[i]

    // If we are at the last key, set the value
    if (i === keys.length - 1) {
      Vue.set(current, key, value)
    } else {
      // If the key does not exist or is not an object, create an empty object or array
      if (!(key in current) || typeof current[key] !== 'object') {
        // Check if the next key is a number to decide between object or array
        Vue.set(current, key, isNaN(keys[i + 1]) ? {} : [])
      }
      // Move to the next level in the object
      current = current[key]
    }
  }
}

/**
 * Uses Object.defineProperty to make Vue provide/inject reactive.
 *
 * @param staticProperties The original object
 * @param reactiveProperties An object containing the properties and values to
 *                           become reactive
 * @return {object} The original object with the updated properties
 * @see https://stackoverflow.com/questions/65718651/how-do-i-make-vue-2-provide-inject-api-reactive
 *
 * @example
 * const obj = { a: "A", b: "B" }
 * fixPropertyReactivityForProvide(obj, { c: () => "C" }
 * console.log(obj.c) // "c" property is now reactive and will return "C"
 */
export function fixPropertyReactivityForProvide(
  staticProperties,
  reactiveProperties
) {
  Object.entries(reactiveProperties).forEach(([propertyName, getValue]) => {
    Object.defineProperty(staticProperties, propertyName, {
      enumerable: true,
      get: () => getValue(),
    })
  })
  return staticProperties
}
