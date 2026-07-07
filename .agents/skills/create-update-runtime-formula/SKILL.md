---
name: Runtime Formulas
description: Create or update Baserow runtime formulas in `core/formula/runtime_formula_types.py`. Use when adding or updating a runtime formula.
version: 1.0.0
---

# Create Or Update Runtime Formulas

Use this skill when a task involves creating or updating a Baserow runtime formula.

Runtime formulas are used in the Application builder, Automation builder, and the AIField in the Database builder. Any changes made to runtime formulas must be compatible with all three parts of the codebase.

The runtime formulas need to be implemented in both the backend and the frontend. In the backend, the runtime formulas are evaluated at runtime. In the frontend, the corresponding runtime formulas are used to validate correct syntax.

This repo already has the core patterns. Prefer copying an existing implementation close to the target behavior, and then modifying it to support the new requirements, instead of inventing a new structure.

## First Step

Before adding a new runtime formula type, identify whether a new argument type is needed.

Note that both the backend and frontend define `parse_args()` and `parseArgs()` respectively, which uses the argument type's `parse()` to transform arguments before they are executed.

There are some additional methods that control how the formula is rendered in the rich text formula editor, but most simple formulas shouldn't need to override them:
- `toNode()`
- `formulaComponentType()`
- `formulaComponent()`
- `fromNodeToFormula()`

## Ensurers
Ensurers are reusable normalization/coercion functions that convert an arbitrary value into a specific type, or raise an error if conversion is not possible. They live in:
- Backend: `backend/src/baserow/core/formula/validator.py`
- Frontend: `web-frontend/modules/core/utils/validator.js`

Existing ensurers include `ensure_string`, `ensure_duration`, etc.

### When to create or use an ensurer
Argument types should delegate their `test()` and `parse()` methods to an ensurer rather than implementing inline conversion logic.
- For `test()`, call the ensurer inside a try/except (backend) or try/catch (frontend) and return `True`/`False`.
- For `parse()`, return the ensurer's result directly.

Runtime formula types should use ensurers in their `execute()` method when converting input values, rather than calling low-level conversion functions (e.g. `datetime.strptime()`, `moment()`) directly.

Before creating a new ensurer, check whether an existing one already covers the target type. Only create a new ensurer when no existing one handles the conversion.

### When a new type is introduced, update existing ensurers
When introducing a new data type (e.g. `timedelta` / `Timedelta`), the existing `ensure_string()` and `ensure_integer()` ensurers may need to be updated to handle coercion of the new type into strings and integers.

For example:
- `ensure_string()` was updated to convert `timedelta` to a human-readable string like `"1 day"`
- `ensure_integer()` was updated to convert `timedelta` to total seconds.

### Ensurer implementation conventions
- Backend ensurers raise `django.core.exceptions.ValidationError` on failure.
- Frontend ensurers throw `TypeError` or `Error` on failure.
- Both backend and frontend ensurers must implement the same conversion logic and accept the same range of input types.
- Tests for ensurers go in:
  - Backend: `backend/tests/baserow/core/formula/test_validator.py`
  - Frontend: `web-frontend/test/unit/core/utils/validator.spec.js`

## Backend Checklist

Useful backend files:
- Runtime formula types: `backend/src/baserow/core/formula/runtime_formula_types.py`
- Runtime formula argument types: `backend/src/baserow/core/formula/argument_types.py`
- Register new runtime formula types in: `backend/src/baserow/core/apps.py`
- Tests for runtime formula types: `backend/tests/baserow/core/formula/test_runtime_formula_types.py`

### Runtime Formula Type

A new runtime formula type should subclass `RuntimeFormulaFunction` and implement the following properties and methods.

#### `type`

This is a unique lower-cased and snake-cased identifier.

#### `args`

This is a list of argument types.

If the argument type or length are dynamic or optional, `min_args`, `validate_type_of_args()`, and `validate_number_of_args()` will likely also need to be implemented.

As a general rule, prefer to use a more permissive argument type when possible. E.g. `RuntimeConcat` allows 2 or more arguments. Each argument is coerced to a string. This allows `concat()` to concatenate a mix of ints, floats, and strings to produce a result.

#### `execute()`

This method should compute and return the expected result for the runtime formula type.

### Runtime Formula Argument Type

The runtime formula argument type defines the acceptable arguments for a runtime formula types. The most permissive argument type is `AnyBaserowRuntimeFormulaArgumentType`, which will accept any argument type, such as int, string, etc.

When creating a new runtime formula type, consider whether a new argument type is necessary or whether an existing argument type is already available that satisfies the requirements.

Note that the constructor can accept kwargs, such as `cast_to_int` for `NumberBaserowRuntimeFormulaType`. E.g. `RuntimeRound` uses `optional=True, cast_to_int=True`.

All argument types must implement both `test()` and `parse()`. The `get_error_message()` method is special, which is described next.

Argument types should delegate to an ensurer in `validator.py` for their `test()` and `parse()` implementations. For example, `DurationBaserowRuntimeFormulaArgumentType` delegates to `ensure_duration()`. Avoid duplicating conversion logic inline when an ensurer exists or can be created.

##### `get_error_message()`
When an argument type can return a useful human-readable error message, this method should be overridden to return an error message.

E.g. the `TimezoneBaserowRuntimeFormulaArgumentType` argument type overrides `get_error_message()` to return a human-readable error message when the timezone value is invalid.

### Register the Runtime Formula Type

After creating a new runtime formula type, it must be imported and registered in `backend/src/baserow/core/apps.py`.

The syntax is: `formula_runtime_function_registry.register(RuntimeFoo())`

### Tests

For new runtime formula types, tests should be added in `test_runtime_formula_types.py`. Notice that existing tests ensure that:
- The `execute()` method returns the expected result.
- The `validate_type_of_args()` correctly validates various possible inputs, and either returns `None` to indicate that the argument is allowed, or returns the same argument back to indicate it is an invalid argument.
- The `validate_number_of_args()` method returns a bool where `True` indicates the number of arguments are valid, and `False` otherwise.
- If the argument type's `get_error_message()` is overridden:
  - A relevant test for the argument type's method should be added to `test_argument_types.py`.
  - A relevant test for the runtime formula type should be added to `test_runtime_formula_types.py`.

## Frontend Checklist

The frontend needs a parallel implementation of the backend changes in order to support validating the syntax of the runtime formula.

Useful frontend files:
- Runtime formula types: `web-frontend/modules/core/runtimeFormulaTypes.js`
- Runtime formula argument types: `web-frontend/modules/core/runtimeFormulaArgumentTypes.js`
- Register new runtime formula types in: `web-frontend/modules/core/plugin.js`
- Tests for runtime formula types: `web-frontend/test/unit/core/formula/runtimeFormulaTypes.spec.js`
- Translations for runtime formula descriptions: `web-frontend/locales/en.json`
- Re-usable utility functions should be added in: `web-frontend/modules/core/utils/`
- Enums are defined in: `web-frontend/modules/core/enums.js`

### Runtime Formula Type

A new runtime formula type should extend the RuntimeFormulaFunction class. It should implement the following methods.

#### `getType()`

This corresponds to the backend's `RuntimeFormulaFunction`'s `type` property and should be an exact match.

#### `getFormulaType()`

This defines the formula type as an enum. Possible choices are `FORMULA_TYPE.FUNCTION` if the runtime formula type is a function like `concat()`, or `FORMULA_TYPE.OPERATOR` if it is an operator such as `=`, `+`, etc.

#### `getCategoryType()`

This defines how the runtime formula type is categorized and grouped in the frontend. Pick one of the enum options in `FORMULA_CATEGORY`.

#### `execute()`

The `execute()` method should return the desired result of the runtime formula being called. The behaviour should be identical to the backend's corresponding `execute()` implementation.

#### `args` getter

This getter property corresponds to the backend's `args` property. It should return an array of argument types.

If the argument type or length are dynamic or optional, `numArgs()`, `validateArgs()`, and `validateNumberOfArgs()` will likely also need to be implemented.

As a general rule, prefer to use a more permissive argument type when possible. E.g. `RuntimeConcat` allows 2 or more arguments. Each argument is coerced to a string. This allows `concat()` to concatenate a mix of ints, floats, and strings to produce a result.

#### `validateNumberOfArgs()`

This corresponds to the backend's `validate_number_of_args()` method and should implement the same behaviour.

#### `validateArgs()`

This is a higher level method that internally calls `validateTypeOfArgs()` (corresponds to the backend's `validate_type_of_args()` method). It can be overridden for custom validation logic. It should implement the same behaviour as the backend logic.

An important point to note is that in the validation visitor, there will be additional context that can provide additional context to help with validation. This is not available to the execution visitor.

#### `getOperatorSymbol` getter

This getter property should only be implemented when the `getFormulaType()` returns an operator. It should return a operator symbol, e.g. `+`, `-`, `>=`, etc.

#### `getDescription()`

This should return a description of the runtime formula type. The description should be added to 
the `runtimeFormulaTypes` dict in `web-frontend/locales/en.json`.

#### `getExamples()`

This should return an array of objects. Each object should define the `formula` and `result` keys. The `formula` value should be and example of how to use the runtime formula, and the `result` value should show an example of the expected result of calling the runtime formula.

### Runtime Formula Argument Type

Similar to the corresponding backend implementation, the runtime formula argument type defines the acceptable arguments for a runtime formula types and are defined in `web-frontend/modules/core/runtimeFormulaArgumentTypes.js`.

The most permissive argument type is `AnyBaserowRuntimeFormulaArgumentType`, which will accept any argument type, such as int, string, etc.

When creating a new runtime formula type, consider whether a new argument type is necessary or whether an existing argument type is already available that satisfies the requirements. If a new type is created for the backend, the frontend will likely also need a new type.

All argument types must implement both `test()` and `parse()`. The `getErrorMessage()` method is special, which is described next.

##### `getErrorMessage()`
When an argument type can return a useful human-readable error message, this method should be overridden with a key defined in the `runtimeFormulaTypeErrors` translation key.

E.g. the `TimezoneBaserowRuntimeFormulaArgumentType` argument type overrides `getErrorMessage()` to return a human-readable error message when the timezone value is invalid.

### Register the Runtime Formula Type

After creating a new runtime formula type, it must be imported and registered in `web-frontend/modules/core/plugin.js`.

Add the new runtime formula to the `fns` array.

### Tests

For new runtime formula types, tests should be added in `runtimeFormulaTypes.spec.js`. Notice that existing tests ensure that:
- The entire runtime formula type's tests are grouped by a `describe()` scope.
- The `execute()`, `validateTypeOfArgs()`, and `validateNumberOfArgs()` are tested with parameterized tests, similar to the corresponding backend tests.
- If the argument type's `getErrorMessage()` is overridden:
  - A relevant test for the argument type's method should be added to `runtimeFormulaArgumentTypes.spec.js`.
  - A relevant test for the runtime formula type should be added to `runtimeFormulaTypes.spec.js`.

## How to Implement

### Creating a new Runtime Formula Type

When creating a new runtime formula type, both the backend and frontend will need parallel implementations:
- Create the new runtime formula type.
  - Backend: `backend/src/baserow/core/formula/runtime_formula_types.py`
  - Frontend: `web-frontend/modules/core/runtimeFormulaTypes.js`
- Create a new argument type if an existing type doesn't provide the needed functionality.
  - Backend: `backend/src/baserow/core/formula/argument_types.py`
  - Frontend: `web-frontend/modules/core/runtimeFormulaArgumentTypes.js`
- Create or update an ensurer if the argument type or `execute()` method requires type coercion that isn't covered by an existing ensurer.
  - Backend: `backend/src/baserow/core/formula/validator.py`
  - Frontend: `web-frontend/modules/core/utils/validator.js`
- If introducing a new data type, check whether existing ensurers (e.g. `ensure_string()`, etc) need updating to handle coercion of the new type.
- Add tests for new or updated ensurers.
  - Backend: `backend/tests/baserow/core/formula/test_validator.py`
  - Frontend: `web-frontend/test/unit/core/utils/validator.spec.js`
- Register the runtime formula type.
  - Backend: `backend/src/baserow/core/apps.py`
  - Frontend: `web-frontend/modules/core/plugin.js`
- Add tests.
  - Backend: `backend/tests/baserow/core/formula/test_runtime_formula_types.py`
  - Frontend: `web-frontend/test/unit/core/formula/runtimeFormulaTypes.spec.js`

The frontend will additionally need translations for the description: `web-frontend/locales/en.json`.

### Updating an existing Runtime Formula Type

When updating an existing runtime formula type, ensure that both the backend and frontend have:
- Matching implementations.
- Tests are updated.
- Translations are updated.

## Guardrails

Do not add a new runtime formula type or an argument type, without first checking that an existing formula type or argument type already provides similar functionality.

If an existing type can be minimally refactored to support the new requirements, suggest a refactor.
