import traceback
from copy import deepcopy
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import connection
from django.db.models import Prefetch, QuerySet
from django.db.utils import DatabaseError, DataError, ProgrammingError

from loguru import logger
from opentelemetry import trace

from baserow.contrib.database.db.schema import (
    lenient_schema_editor,
    safe_django_schema_editor,
)
from baserow.contrib.database.db.sql_queries import (
    sql_create_try_cast,
    sql_drop_try_cast,
)
from baserow.contrib.database.fields.constants import (
    RESERVED_BASEROW_FIELD_NAMES,
    UPSERT_OPTION_DICT_KEY,
    DeleteFieldStrategyEnum,
)
from baserow.contrib.database.fields.field_converters import (
    MultipleSelectConversionConfig,
)
from baserow.contrib.database.fields.models import TextField
from baserow.contrib.database.fields.operations import (
    CreateFieldOperationType,
    DeleteFieldOperationType,
    DuplicateFieldOperationType,
    ReadFieldOperationType,
    UpdateFieldOperationType,
)
from baserow.contrib.database.fields.utils.field_constraint import (
    _create_constraint_objects,
    build_django_field_constraints,
    validate_default_value_with_constraints,
    validate_field_constraints,
)
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.db import specific_iterator, sql
from baserow.core.handler import CoreHandler
from baserow.core.models import TrashEntry, User
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.trash.exceptions import RelatedTableTrashedException
from baserow.core.trash.handler import TrashHandler
from baserow.core.trash.registries import trash_item_type_registry
from baserow.core.utils import (
    ChildProgressBuilder,
    extract_allowed,
    find_unused_name,
    set_allowed_attrs,
)

from ..search.handler import SearchHandler
from ..table.cache import invalidate_table_in_model_cache
from .backup_handler import FieldDataBackupHandler
from .dependencies.handler import FieldDependencyHandler
from .dependencies.update_collector import FieldUpdateCollector
from .exceptions import (
    CannotChangeFieldType,
    CannotDeletePrimaryField,
    DbIndexNotSupportedError,
    FailedToLockFieldDueToConflict,
    FieldConstraintException,
    FieldDoesNotExist,
    FieldIsAlreadyPrimary,
    FieldNotInTable,
    FieldWithSameNameAlreadyExists,
    ImmutableFieldProperties,
    IncompatibleFieldTypeForUniqueValues,
    IncompatiblePrimaryFieldTypeError,
    InvalidBaserowFieldName,
    MaxFieldLimitExceeded,
    MaxFieldNameLengthExceeded,
    PrimaryFieldAlreadyExists,
    ReservedBaserowFieldNameException,
    TableHasNoPrimaryField,
)
from .field_cache import FieldCache
from .models import Field, FieldConstraint, SelectOption, SpecificFieldForUpdate
from .registries import field_converter_registry, field_type_registry
from .signals import (
    before_field_deleted,
    field_created,
    field_deleted,
    field_restored,
    field_updated,
)

tracer = trace.get_tracer(__name__)


def _validate_field_name(
    field_values: Dict[str, Any],
    table: Table,
    existing_field: Optional[Field] = None,
    raise_if_name_missing: bool = True,
):
    """
    Raises various exceptions if the provided field name is invalid.

    :param field_values: The dictionary which should contain a name key.
    :param table: The table to check that this field name is valid for.
    :param existing_field: If this is name change for an existing field then the
        existing field instance must be provided here.
    :param raise_if_name_missing: When True raises a InvalidBaserowFieldName if the
        name key is not in field_values. When False does not return and immediately
        returns if the key is missing.
    :raises InvalidBaserowFieldName: If "name" is
    :raises MaxFieldNameLengthExceeded: When a provided field name is too long.
    :return:
    """

    if "name" not in field_values:
        if raise_if_name_missing:
            raise InvalidBaserowFieldName()
        else:
            return

    name = field_values["name"]
    if existing_field is not None and existing_field.name == name:
        return

    max_field_name_length = Field.get_max_name_length()
    if len(name) > max_field_name_length:
        raise MaxFieldNameLengthExceeded(max_field_name_length)

    if name.strip() == "":
        raise InvalidBaserowFieldName()

    if Field.objects.filter(table=table, name=name).exists():
        raise FieldWithSameNameAlreadyExists(
            f"A field already exists for table '{table.name}' with the name '{name}'."
        )

    if name in RESERVED_BASEROW_FIELD_NAMES:
        raise ReservedBaserowFieldNameException(
            f"A field named {name} cannot be created as it already exists as a "
            f"reserved Baserow field name."
        )


T = TypeVar("T", bound="Field")


class FieldHandler(metaclass=baserow_trace_methods(tracer)):
    def get_field(
        self,
        field_id: int,
        field_model: Optional[Type[T]] = None,
        base_queryset: Optional[QuerySet] = None,
    ) -> T:
        """
        Selects a field with a given id from the database.

        :param field_id: The identifier of the field that must be returned.
        :param field_model: If provided that model's objects are used to select the
            field. This can for example be useful when you want to select a TextField or
            other child of the Field model.
        :param base_queryset: The base queryset from where to select the field.
            object. This can for example be used to do a `select_related`. Note that
            if this is used the `field_model` parameter doesn't work anymore.
        :raises FieldDoesNotExist: When the field with the provided id does not exist.
        :return: The requested field instance of the provided id.
        :rtype: Field
        """

        if not field_model:
            field_model = Field

        if base_queryset is None:
            base_queryset = field_model.objects

        try:
            field = base_queryset.select_related("table__database__workspace").get(
                id=field_id
            )
        except Field.DoesNotExist:
            raise FieldDoesNotExist(f"The field with id {field_id} does not exist.")

        if TrashHandler.item_has_a_trashed_parent(field.table, check_item_also=True):
            raise FieldDoesNotExist(f"The field with id {field_id} does not exist.")

        return field

    def get_base_fields_queryset(self) -> QuerySet[Field]:
        """
        Returns a base queryset with proper select and prefetch related fields to use in
        queries that need to fetch fields.

        :return: A queryset with select and prefetch related fields set.
        """

        return Field.objects.select_related(
            "content_type", "table__database__workspace"
        ).prefetch_related(
            Prefetch(
                "table__database__workspace__users",
                queryset=User.objects.filter(profile__to_be_deleted=False).order_by(
                    "first_name"
                ),
                to_attr="available_collaborators",
            ),
            "select_options",
            "field_constraints",
        )

    def get_fields(
        self,
        table: Table,
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
    ) -> Union[QuerySet[Field], Iterable[Field]]:
        """
        Gets all fields, optionally their specific subclass, of a given table.

        :param table: The table we want to query fields from.
        :param specific: Whether we want each field's specific subclass.
        :param base_queryset: The base queryset to use to build the query.
        :return: An iterable of fields.
        """

        queryset = base_queryset if base_queryset is not None else table.field_set.all()

        if specific:
            queryset = specific_iterator(queryset.select_related("content_type"))
        return queryset

    def get_specific_field_for_update(
        self,
        field_id: int,
        field_model: Optional[Type[T]] = None,
    ) -> SpecificFieldForUpdate:
        """
        Returns the .specific field which has been locked FOR UPDATE.

        :param field_id: The field to lock and retrieve the specific instance of.
        :param field_model: The field_model to query using, provide a specific one if
            you want an exception raised if the field is not of this field_model type.
        :return: A specific locked field instance
        """

        queryset = Field.objects.select_related("table").select_for_update(
            of=("self", "table"), nowait=settings.BASEROW_NOWAIT_FOR_LOCKS
        )

        try:
            specific_field = self.get_field(
                field_id, field_model, base_queryset=queryset
            ).specific
        except DatabaseError as e:
            if "could not obtain lock on row" in traceback.format_exc():
                raise FailedToLockFieldDueToConflict() from e
            else:
                raise e

        return cast(
            SpecificFieldForUpdate,
            specific_field,
        )

    def create_field(
        self,
        user: AbstractUser,
        table: Table,
        type_name: str,
        primary: bool = False,
        skip_django_schema_editor_add_field: bool = True,
        return_updated_fields: bool = False,
        primary_key: bool = None,
        skip_search_updates: bool = False,
        description: Optional[str] = None,
        init_field_data: bool = False,
        **kwargs,
    ) -> Union[Field, Tuple[Field, List[Field]]]:
        """
        Creates a new field with the given type for a table.

        :param user: The user on whose behalf the field is created.
        :param table: The table that the field belongs to.
        :param type_name: The type name of the field. Available types can be found in
            the field_type_registry.
        :param primary: Every table needs at least a primary field which cannot be
            deleted and is a representation of the whole row.
        :param skip_django_schema_editor_add_field: Indicates whether the
            actual database schema change has to be made. You may want to do this
            if you are making two Baserow fields which share the same m2m table. For
            the second field you create, you don't want to create the m2m table again.
        :param return_updated_fields: When True any other fields who changed as a
            result of this field creation are returned with their new field instances.
        :param primary_key: The id of the field.
        :param skip_search_updates: Whether to trigger a search update for
            this field creation.
        :param description: The description of the field.
        :param init_field_data: Whether to initialize the field with data.
        :param kwargs: The field values that need to be set upon creation.

        :raises PrimaryFieldAlreadyExists: When we try to create a primary field,
            but one already exists.
        :raises MaxFieldLimitExceeded: When we try to create a field,
            but exceeds the field limit.
        :return: The created field instance. If return_updated_field is set then any
            updated fields as a result of creating the field are returned in a list
            as a second tuple value.
        """

        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user, CreateFieldOperationType.type, workspace=workspace, context=table
        )

        # Because only one primary field per table can exist and we have to check if one
        # already exists. If so the field cannot be created and an exception is raised.
        if primary and Field.objects.filter(table=table, primary=True).exists():
            raise PrimaryFieldAlreadyExists(
                f"A primary field already exists for the table {table}."
            )
        field_constraints = kwargs.get("field_constraints", None) or []

        # Figure out which model to use and which field types are allowed for the given
        # field type.
        field_type = field_type_registry.get(type_name)
        model_class = field_type.model_class
        allowed_fields = [
            "name",
            "read_only",
            "immutable_type",
            "immutable_properties",
            "db_index",
        ] + field_type.allowed_fields
        field_values = extract_allowed(kwargs, allowed_fields)
        last_order = model_class.get_last_order(table)

        if primary and not field_type.can_be_primary_field(field_values):
            raise IncompatiblePrimaryFieldTypeError(field_type.type)

        num_fields = table.field_set.count()
        if (num_fields + 1) > settings.MAX_FIELD_LIMIT:
            raise MaxFieldLimitExceeded(
                f"Fields count exceeds the limit of {settings.MAX_FIELD_LIMIT}"
            )

        _validate_field_name(field_values, table)

        field_values = field_type.prepare_values(field_values, user)
        before = field_type.before_create(
            table,
            primary,
            field_values,
            last_order,
            user,
            kwargs,
        )

        instance = model_class(
            table=table,
            order=last_order,
            primary=primary,
            pk=primary_key,
            description=description,
            **field_values,
        )

        validate_field_constraints(field_type, field_constraints)

        validate_default_value_with_constraints(
            field_type, field_constraints, field_values, None
        )

        field_cache = FieldCache()
        instance.save(field_cache=field_cache, raise_if_invalid=True)

        if field_constraints:
            FieldConstraint.objects.bulk_create(
                [
                    FieldConstraint(field=instance, type_name=constraint["type_name"])
                    for constraint in field_constraints
                ]
            )
        FieldDependencyHandler.rebuild_or_raise_if_user_doesnt_have_permissions_after(
            workspace, user, instance, field_cache, ReadFieldOperationType.type
        )

        if instance.db_index and not field_type.can_have_db_index(instance):
            raise DbIndexNotSupportedError(field_type.type)

        # Add the field to the table schema.
        with safe_django_schema_editor(atomic=False) as schema_editor:
            to_model = instance.table.get_model(field_ids=[], fields=[instance])
            model_field = to_model._meta.get_field(instance.db_column)

            if skip_django_schema_editor_add_field:
                schema_editor.add_field(to_model, model_field)

            if field_constraints:
                constraint_objects = _create_constraint_objects(
                    instance, field_constraints
                )
                new_constraints = build_django_field_constraints(
                    instance, constraint_objects
                )
                for constraint in new_constraints:
                    try:
                        schema_editor.add_constraint(to_model, constraint)
                    except Exception:
                        raise FieldConstraintException(
                            f"Could not add constraint {constraint.name} on field {instance.name}."
                        )

        field_type.after_create(
            instance,
            to_model,
            user,
            connection,
            before,
            kwargs,
        )

        if init_field_data:
            field_type.init_field_data(instance, to_model)

        field_cache.cache_model_fields(to_model)
        update_collector = FieldUpdateCollector(table)
        updated_fields = self._update_dependencies_of_field_created(
            instance,
            update_collector,
            field_cache,
            skip_search_updates,
        )
        SearchHandler.schedule_update_search_data(table, fields=[instance])

        field_created.send(
            self,
            field=instance,
            user=user,
            related_fields=updated_fields,
            type_name=type_name,
        )
        update_collector.send_additional_field_updated_signals()

        if return_updated_fields:
            return instance, updated_fields
        else:
            return instance

    def _update_dependencies_of_field_created(
        self, field, update_collector, field_cache, skip_search_updates
    ):
        updated_fields = []

        all_dependent_fields_grouped_by_depth = (
            FieldDependencyHandler.group_all_dependent_fields_by_level(
                field.table_id,
                [field.id],
                field_cache,
                associated_relations_changed=True,
                database_id_prefilter=field.table.database_id,
            )
        )
        for dependant_fields_group in all_dependent_fields_grouped_by_depth:
            for (
                dependant_field,
                dependant_field_type,
                path_to_starting_table,
            ) in dependant_fields_group:
                dependant_field_type.field_dependency_created(
                    dependant_field,
                    field,
                    update_collector,
                    field_cache,
                    path_to_starting_table,
                )
            updated_fields += update_collector.apply_updates_and_get_updated_fields(
                field_cache,
                skip_search_updates,
                skip_fields_type_changed=True,
                skip_rebuild_field_dependencies=True,
            )

        update_collector.apply_fields_type_changed(field_cache)
        update_collector.apply_rebuild_field_dependencies(field_cache)

        return updated_fields

    def update_field(
        self,
        user: AbstractUser,
        field: SpecificFieldForUpdate,
        new_type_name: Optional[str] = None,
        return_updated_fields: bool = False,
        postfix_to_fix_name_collisions: Optional[str] = None,
        after_schema_change_callback: Optional[
            Callable[[SpecificFieldForUpdate], None]
        ] = None,
        **kwargs,
    ) -> Union[SpecificFieldForUpdate, Tuple[SpecificFieldForUpdate, List[Field]]]:
        """
        Updates the values and/or type of the given field.

        :param user: The user on whose behalf the table is updated.
        :param field: The field instance that needs to be updated.
        :param new_type_name: If the type needs to be changed it can be
            provided here.
        :param return_updated_fields: When True any other fields who changed as a
            result of this field update are returned with their new field instances.
        :param postfix_to_fix_name_collisions: If provided and the field name
            already exists in the table, the specified postfix will be added to the
            field name and possibly incremented until a unique unused name is found.
            If this parameter is not set instead an exception will be raised if
            the field name already exists.
        :param after_schema_change_callback: If specified this callback is called
            after the field has had it's schema updated but before any dependant
            fields have been updated.
        :param kwargs: The field values that need to be updated
        :raises ValueError: When the provided field is not an instance of Field.
        :raises CannotChangeFieldType: When the database server responds with an
            error while trying to change the field type. This should rarely happen
            because of the lenient schema editor, which replaces the value with null
            if it could not be converted.
        :return: A data class containing information on all the changes made as a result
            of the field update.
        """

        if not isinstance(field, Field):
            raise ValueError("The field is not an instance of Field.")

        if type(field) is Field:
            raise ValueError(
                "The field must be a specific instance of Field and not the base type "
                "Field itself."
            )

        table = field.table
        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user, UpdateFieldOperationType.type, workspace=workspace, context=field
        )

        old_field = deepcopy(field)
        from_field_type = field_type_registry.get_by_model(field)
        from_model = table.get_model(field_ids=[], fields=[field])
        to_field_type_name = new_type_name or from_field_type.type

        # If the provided field type does not match with the current one we need to
        # migrate the field to the new type.
        baserow_field_type_changed = from_field_type.type != to_field_type_name
        field_cache = FieldCache()

        # Get field_constraints from kwargs, defaulting to None if not provided
        # This preserves existing constraints when not included in PATCH requests
        field_constraints = kwargs.get("field_constraints", None)

        if baserow_field_type_changed:
            to_field_type = field_type_registry.get(to_field_type_name)
        else:
            to_field_type = from_field_type

        allowed_fields = [
            "name",
            "description",
            "read_only",
            "immutable_type",
            "immutable_properties",
            "db_index",
        ] + to_field_type.allowed_fields
        field_values = extract_allowed(kwargs, allowed_fields)

        if field.primary and not to_field_type.can_be_primary_field(field_values):
            raise IncompatiblePrimaryFieldTypeError(to_field_type_name)

        old_constraints = list(old_field.field_constraints.all())
        old_constraint_names = set([c.type_name for c in old_constraints])

        # Only process constraints if they were provided
        if field_constraints is not None:
            new_constraint_names = {c["type_name"] for c in field_constraints}
            field_constraints_changed = old_constraint_names != new_constraint_names
        else:
            field_constraints_changed = False

        if field_constraints_changed and (
            field.read_only or field.immutable_properties
        ):
            raise ImmutableFieldProperties(
                "Field constraints cannot be modified on readonly or immutable fields."
            )

        if baserow_field_type_changed:
            ViewHandler().before_field_type_change(field)
            dependants_broken_due_to_type_change = (
                from_field_type.get_dependants_which_will_break_when_field_type_changes(
                    field, to_field_type, field_cache
                )
            )
            new_model_class = to_field_type.model_class
            field.change_polymorphic_type_to(new_model_class)
            needs_to_update_search_data = True
        else:
            dependants_broken_due_to_type_change = []
            needs_to_update_search_data = from_field_type.should_update_search_data(
                old_field, field_values
            )

        self._validate_name_and_optionally_rename_if_collision(
            field, field_values, postfix_to_fix_name_collisions
        )

        if field_constraints is not None:
            validate_field_constraints(to_field_type, field_constraints)
            validate_default_value_with_constraints(
                to_field_type, field_constraints, field_values, field
            )
        elif baserow_field_type_changed and old_constraints:
            existing_constraint_data = [
                {"type_name": c.type_name} for c in old_constraints
            ]
            validate_field_constraints(to_field_type, existing_constraint_data)
            validate_default_value_with_constraints(
                to_field_type, existing_constraint_data, field_values, field
            )

        field_values = to_field_type.prepare_values(field_values, user)
        before = to_field_type.before_update(old_field, field_values, user, kwargs)

        field = set_allowed_attrs(field_values, allowed_fields, field)

        field.save(field_cache=field_cache, raise_if_invalid=True)

        if field_constraints is not None and field_constraints_changed:
            field.field_constraints.exclude(type_name__in=new_constraint_names).delete()

            existing_names = set([c.type_name for c in field.field_constraints.all()])
            constraints_to_create = new_constraint_names - existing_names
            if constraints_to_create:
                field.field_constraints.bulk_create(
                    [
                        FieldConstraint(field=field, type_name=type_name)
                        for type_name in constraints_to_create
                    ]
                )
        FieldDependencyHandler.rebuild_or_raise_if_user_doesnt_have_permissions_after(
            workspace, user, field, field_cache, ReadFieldOperationType.type
        )

        if field.db_index and not to_field_type.can_have_db_index(field):
            # If the user explicitly set the `db_index` to true, but it's not
            # compatible, then we want to fail hard so that the user is aware.
            raise DbIndexNotSupportedError(to_field_type.type)

        # If no converter is found we are going to convert to field using the
        # lenient schema editor which will alter the field's type and set the data
        # value to null if it can't be converted.
        to_model = field.table.get_model(field_ids=[], fields=[field])
        from_model_field = from_model._meta.get_field(field.db_column)
        to_model_field = to_model._meta.get_field(field.db_column)

        update_collector = FieldUpdateCollector(field.table)

        # If the field type or the database representation changes it could be
        # that some view dependencies like filters or sortings need to be changed.
        if (
            baserow_field_type_changed
            or not from_field_type.has_compatible_model_fields(
                from_model_field, to_model_field
            )
        ):
            update_collector.add_to_fields_type_changed(field)

        # Before a field is updated we are going to call the before_schema_change
        # method of the old field because some cleanup of related instances might
        # need to happen.
        from_field_type.before_schema_change(
            old_field,
            field,
            from_model,
            to_model,
            from_model_field,
            to_model_field,
            user,
            kwargs,
        )

        # Try to find a data converter that can be applied.
        converter = field_converter_registry.find_applicable_converter(
            from_model, old_field, field
        )

        if converter:
            # If a field data converter is found we are going to use that one to alter
            # the field and maybe do some data conversion.
            converter.alter_field(
                old_field,
                field,
                from_model,
                to_model,
                from_model_field,
                to_model_field,
                user,
                connection,
            )
        else:
            if baserow_field_type_changed:
                # If the baserow type has changed we always want to force run any alter
                # column SQL as otherwise it might not run if the two baserow fields
                # share the same underlying database column type.
                force_alter_column = True
            else:
                force_alter_column = to_field_type.force_same_type_alter_column(
                    old_field, field
                )

            # If no field converter is found we are going to alter the field using the
            # the lenient schema editor.
            with lenient_schema_editor(
                from_field_type.get_alter_column_prepare_old_value(
                    connection, old_field, field
                ),
                to_field_type.get_alter_column_prepare_new_value(
                    connection, old_field, field
                ),
                force_alter_column,
            ) as schema_editor:
                try:
                    if baserow_field_type_changed or field_constraints_changed:
                        existing_constraints = build_django_field_constraints(
                            old_field, old_constraints
                        )
                        for constraint in existing_constraints:
                            try:
                                schema_editor.remove_constraint(from_model, constraint)
                            except Exception:
                                raise FieldConstraintException(
                                    f"Could not remove constraint {constraint.name} on field {field.name}."
                                )

                    schema_editor.alter_field(
                        from_model, from_model_field, to_model_field
                    )

                    if (
                        baserow_field_type_changed or field_constraints_changed
                    ) and field_constraints:
                        new_constraint_objects = _create_constraint_objects(
                            field, field_constraints
                        )
                        new_constraints = build_django_field_constraints(
                            field, new_constraint_objects
                        )
                        for constraint in new_constraints:
                            try:
                                schema_editor.add_constraint(to_model, constraint)
                            except Exception:
                                raise FieldConstraintException(
                                    f"Could not add constraint {constraint.name} on field {field.name}."
                                )
                except (ProgrammingError, DataError) as e:
                    # If something is going wrong while changing the schema we will
                    # just raise a specific exception. In the future we want to have
                    # some sort of converter abstraction where the values of certain
                    # types can be converted to another value.
                    logger.error(str(e))
                    message = (
                        f"Could not alter field when changing field type "
                        f"{from_field_type.type} to {to_field_type_name}."
                    )
                    raise CannotChangeFieldType(message)

        from_model_field_type = from_model_field.db_parameters(connection)["type"]
        to_model_field_type = to_model_field.db_parameters(connection)["type"]
        altered_column = from_model_field_type != to_model_field_type

        # If the new field doesn't support select options we can delete those
        # relations.
        if (
            from_field_type.can_have_select_options
            and not to_field_type.can_have_select_options
        ):
            SelectOption.objects.filter(field_id=field.id).delete()

        to_field_type.after_update(
            old_field,
            field,
            from_model,
            to_model,
            user,
            connection,
            altered_column,
            before,
            kwargs,
        )

        if after_schema_change_callback:
            after_schema_change_callback(field)

        field_cache.cache_model_fields(to_model)

        for (
            dependant_field,
            dependant_field_type,
            via_path_to_starting_table,
        ) in dependants_broken_due_to_type_change:
            dependant_field_type.field_dependency_updated(
                dependant_field,
                field,
                old_field,
                update_collector,
                field_cache,
                via_path_to_starting_table,
            )

        updated_fields = update_collector.apply_updates_and_get_updated_fields(
            field_cache
        )

        updated_fields += self._update_dependencies_of_field_updated(
            field, old_field, update_collector, field_cache
        )

        ViewHandler().field_updated(field)
        if needs_to_update_search_data:
            SearchHandler.schedule_update_search_data(field.table, fields=[field])

        field_updated.send(
            self,
            field=field,
            old_field=old_field,
            related_fields=updated_fields,
            field_type_changed=baserow_field_type_changed,
            user=user,
        )
        update_collector.send_additional_field_updated_signals()

        if return_updated_fields:
            return field, updated_fields
        else:
            return field

    def _update_dependencies_of_field_updated(
        self, field, old_field, update_collector, field_cache
    ):
        updated_fields = []
        all_dependent_fields_grouped_by_depth = (
            FieldDependencyHandler.group_all_dependent_fields_by_level(
                field.table_id,
                [field.id],
                field_cache,
                associated_relations_changed=True,
                database_id_prefilter=field.table.database_id,
            )
        )
        for dependant_fields_group in all_dependent_fields_grouped_by_depth:
            for (
                dependant_field,
                dependant_field_type,
                path_to_starting_table,
            ) in dependant_fields_group:
                dependant_field_type.field_dependency_updated(
                    dependant_field,
                    field,
                    old_field,
                    update_collector,
                    field_cache,
                    path_to_starting_table,
                )
            updated_fields += update_collector.apply_updates_and_get_updated_fields(
                field_cache,
                skip_fields_type_changed=True,
                skip_rebuild_field_dependencies=True,
            )

        update_collector.apply_fields_type_changed(field_cache)
        update_collector.apply_rebuild_field_dependencies(field_cache)

        return updated_fields

    def duplicate_field(
        self,
        user: AbstractUser,
        field: Field,
        duplicate_data: bool = False,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Tuple[Field, List[Field]]:
        """
        Duplicates an existing field instance.

        :param user: The user on whose behalf the table is duplicated.
        :param field: The field instance that needs to be duplicated.
        :param duplicate_data: Whether or not the data of the field should be
        :param progress_builder: A progress builder object that can be used to
            report progress.
        :raises ValueError: When the provided table is not an instance of Table.
        :return: A tuple with duplicated field instance and a list of the fields
            that have been updated.
        """

        if not isinstance(field, Field):
            raise ValueError("The field is not an instance of Field")

        progress = ChildProgressBuilder.build(progress_builder, child_total=3)

        database = field.table.database
        CoreHandler().check_permissions(
            user,
            DuplicateFieldOperationType.type,
            workspace=database.workspace,
            context=field,
        )

        specific_field = field.specific
        field_type = field_type_registry.get_by_model(specific_field)
        serialized_field = field_type.export_serialized(specific_field)
        progress.increment()

        new_name = self.find_next_unused_field_name(
            field.table,
            [serialized_field.pop("name")],
        )

        # Remove properties that are unqiue to the field and that must be persistent
        # when copying.
        for key in [
            "id",
            "order",
            "primary",
            "read_only",
            "immutable_type",
            "immutable_properties",
            "search_data_initialized_at",
        ]:
            serialized_field.pop(key, None)

        new_field, updated_fields = self.create_field(
            user,
            field.table,
            field_type.type,
            primary=False,
            name=new_name,
            return_updated_fields=True,
            **serialized_field,
        )
        progress.increment()

        if duplicate_data and field_type.keep_data_on_duplication:
            FieldDataBackupHandler.duplicate_field_data(field, new_field)
        progress.increment()

        return new_field, updated_fields

    def delete_field(
        self,
        user: AbstractUser,
        field: Field,
        existing_trash_entry: Optional[TrashEntry] = None,
        update_collector: Optional[FieldUpdateCollector] = None,
        field_cache: Optional[FieldCache] = None,
        apply_and_send_updates: Optional[bool] = True,
        allow_deleting_primary: Optional[bool] = False,
        delete_strategy: DeleteFieldStrategyEnum = DeleteFieldStrategyEnum.TRASH,
    ) -> List[Field]:
        """
        Deletes an existing field if it is not a primary field.

        :param user: The user on whose behalf the table is created.
        :param field: The field instance that needs to be deleted.
        :param existing_trash_entry: An optional TrashEntry that the handler can
            pass to the trash system to track cascading deletions in a single
            trash entry.
        :param update_collector: An optional update collector which will be used
            to store related field updates in.
        :param field_cache: An optional field cache to be used when fetching
            fields.
        :param apply_and_send_updates: Set to False to disable related field
            updates being applied and any signals from being sent.
        :param allow_deleting_primary: Set to true if its OK for a primary field
            to be deleted.
        :param delete_strategy: Indicates how to delete the field. By default it's
            trashed, but depending on the value is van also just delete the object, or
            permanently delete it immediately.
        :raises ValueError: When the provided field is not an instance of Field.
        :raises CannotDeletePrimaryField: When we try to delete the primary
            field which cannot be deleted.
        :return: A list of fields that have been updated because of the deleted
            field.
        """

        if not isinstance(field, Field):
            raise ValueError("The field is not an instance of Field")

        workspace = field.table.database.workspace
        CoreHandler().check_permissions(
            user, DeleteFieldOperationType.type, workspace=workspace, context=field
        )

        if field.primary and not allow_deleting_primary:
            raise CannotDeletePrimaryField(
                "Cannot delete the primary field of a table."
            )

        field = field.specific
        if update_collector is None:
            update_collector = FieldUpdateCollector(field.table)
        if field_cache is None:
            field_cache = FieldCache()

        all_dependent_fields_grouped_by_depth = list(
            FieldDependencyHandler.group_all_dependent_fields_by_level(
                field.table_id,
                [field.id],
                field_cache,
                associated_relations_changed=True,
                database_id_prefilter=field.table.database_id,
            )
        )
        before_return = before_field_deleted.send(
            self,
            field_id=field.id,
            field=field,
            user=user,
            allow_deleting_primary=allow_deleting_primary,
        )

        FieldDependencyHandler.break_dependencies_delete_dependants(field)

        if delete_strategy == DeleteFieldStrategyEnum.PERMANENTLY_DELETE:
            from baserow.contrib.database.trash.trash_types import (
                FieldTrashableItemType,
            )

            trash_item_type_registry.get(
                FieldTrashableItemType.type
            ).permanently_delete_item(field)
        elif delete_strategy == DeleteFieldStrategyEnum.DELETE_OBJECT:
            field.delete()
        else:
            existing_trash_entry = TrashHandler.trash(
                user,
                workspace,
                field.table.database,
                field,
                existing_trash_entry=existing_trash_entry,
            )
        # The trash call above might have just caused a massive field update to lots of
        # different fields. We need to reset our cache accordingly.
        field_cache.reset_cache()
        updated_fields = self._update_dependencies_of_field_deleted(
            field, update_collector, field_cache, all_dependent_fields_grouped_by_depth
        )

        if delete_strategy == DeleteFieldStrategyEnum.TRASH:
            field_type = field_type_registry.get_by_model(field)
            related_fields_to_trash = [
                f
                for f in field_type.get_other_fields_to_trash_restore_always_together(
                    field
                )
                if not f.trashed
            ]
            for related_field in related_fields_to_trash:
                self.delete_field(
                    user, related_field, existing_trash_entry=existing_trash_entry
                )

        if apply_and_send_updates:
            field_deleted.send(
                self,
                field_id=field.id,
                field=field,
                related_fields=updated_fields,
                user=user,
                before_return=before_return,
            )
            update_collector.send_additional_field_updated_signals()
        return list(updated_fields)

    def _update_dependencies_of_field_deleted(
        self,
        field,
        update_collector,
        field_cache,
        all_dependent_fields_grouped_by_depth,
    ):
        updated_fields = []
        for dependant_fields_group in all_dependent_fields_grouped_by_depth:
            for (
                dependant_field,
                dependant_field_type,
                path_to_starting_table,
            ) in dependant_fields_group:
                dependant_field_type.field_dependency_deleted(
                    dependant_field,
                    field,
                    update_collector,
                    field_cache,
                    path_to_starting_table,
                )

            updated_fields += update_collector.apply_updates_and_get_updated_fields(
                field_cache,
                skip_fields_type_changed=True,
                skip_rebuild_field_dependencies=True,
            )

        update_collector.apply_fields_type_changed(field_cache)
        update_collector.apply_rebuild_field_dependencies(field_cache)

        return updated_fields

    def update_field_select_options(self, user, field, select_options):
        """
        Brings the select options in the desired provided state in a query efficient
        manner.

        Example: select_options = [
            {'id': 1, 'value': 'Option 1', 'color': 'blue'},
            {'value': 'Option 2', 'color': 'red'}
        ]

        :param user: The user on whose behalf the change is made.
        :type user: User
        :param field: The field of which the select options must be updated.
        :type field: Field
        :param select_options: A list containing dicts with the desired select options.
        :type select_options: list
        """

        workspace = field.table.database.workspace
        CoreHandler().check_permissions(
            user, UpdateFieldOperationType.type, workspace=workspace, context=field
        )

        field_type = field_type_registry.get_by_model(field)

        existing_option_ids = [existing.id for existing in field.select_options.all()]

        to_update = []
        to_create = []
        for select_option in select_options:
            create_if_not_exists_id = select_option.get(UPSERT_OPTION_DICT_KEY)
            if create_if_not_exists_id is not None:
                if create_if_not_exists_id in existing_option_ids:
                    to_update.append(create_if_not_exists_id)
                else:
                    to_create.append(select_option)
            elif "id" in select_option:
                to_update.append(select_option["id"])
            else:
                to_create.append(select_option)

        # Checks which option ids must be deleted by comparing the existing ids with
        # the provided ids.
        to_delete = [
            existing for existing in existing_option_ids if existing not in to_update
        ]

        # Call field_type hook before applying modifications
        field_type.before_field_options_update(
            field,
            to_create=to_create,
            to_update=to_update,
            to_delete=to_delete,
        )

        if to_delete:
            SelectOption.objects.filter(field=field, id__in=to_delete).delete()

        instance_to_create = []
        for order, select_option in enumerate(select_options):
            upsert_id = select_option.pop(UPSERT_OPTION_DICT_KEY, None)
            option_id = select_option.pop("id", upsert_id)
            if option_id in existing_option_ids:
                select_option.pop("order", None)
                # Update existing options
                field.select_options.filter(id=option_id).update(
                    **select_option, order=order
                )
            else:
                # Create new instance
                instance_to_create.append(
                    SelectOption(
                        id=upsert_id,
                        field=field,
                        order=order,
                        value=select_option["value"],
                        color=select_option["color"],
                    )
                )

        if instance_to_create:
            SelectOption.objects.bulk_create(instance_to_create)

        # The model has changed when the select options have changed, so we need to
        # invalidate the model cache.
        field.invalidate_table_model_cache()

    # noinspection PyMethodMayBeStatic
    def find_next_unused_field_name(
        self,
        table,
        field_names_to_try: List[str],
        field_ids_to_ignore: Optional[List[int]] = None,
    ) -> str:
        """
        Finds a unused field name in the provided table. If no names in the provided
        field_names_to_try list are available then the last field name in that list will
        have a number appended which ensures it is an available unique field name.
        Respects the maximally allowed field name length. In case the field_names_to_try
        are longer than that, they will get truncated to the maximally allowed length.

        :param table: The table whose fields to search.
        :param field_names_to_try: The field_names to try in order before starting to
            append a number.
        :param field_ids_to_ignore: A list of field id's to exclude from checking to see
            if the field name clashes with.
        :return: An available field name
        """

        if field_ids_to_ignore is None:
            field_ids_to_ignore = []

        max_field_name_length = Field.get_max_name_length()

        # Lookup any existing field names. This way we can skip these and ensure our
        # new field has a unique name.
        existing_field_name_collisions = (
            Field.objects.exclude(id__in=field_ids_to_ignore)
            .filter(table=table)
            .order_by("name")
            .distinct()
            .values_list("name", flat=True)
        )

        return find_unused_name(
            field_names_to_try,
            existing_field_name_collisions,
            max_length=max_field_name_length,
            reserved_names=RESERVED_BASEROW_FIELD_NAMES,
        )

    def restore_field(
        self,
        field: Field,
        update_collector: Optional[FieldUpdateCollector] = None,
        field_cache: Optional[FieldCache] = None,
        send_field_restored_signal: bool = True,
    ):
        """
        Restores the provided field from being in the trashed state.

        :param field: The trashed field to restore.
        :param update_collector: An optional update collector that will be used to
            collect any resulting field updates due to the restore.
        :param field_cache: An optional field cache used to get fields.
        :param send_field_restored_signal: Whether or not a field_restored signal should
            be sent after restoring this field.
        :raises CantRestoreTrashedItem: Raised when this field cannot yet be restored
            due to other trashed items.
        """

        field_type = field_type_registry.get_by_model(field)
        try:
            other_fields_that_must_restore_at_same_time = (
                field_type.get_other_fields_to_trash_restore_always_together(field)
            )
            for other_required_field in other_fields_that_must_restore_at_same_time:
                if other_required_field.table.trashed:
                    raise RelatedTableTrashedException()

            field.name = self.find_next_unused_field_name(
                field.table,
                [field.name, f"{field.name} (Restored)"],
                [field.id],  # Ignore the field itself from the check.
            )
            # We need to set the specific field's name also so when the field_restored
            # serializer switches to serializing the specific instance it picks up and
            # uses the new name set here rather than the name currently in the DB.
            field = field.specific
            field.name = field.name
            field.trashed = False

            if update_collector is None:
                update_collector = FieldUpdateCollector(field.table)
            if field_cache is None:
                field_cache = FieldCache()

            field.save(field_cache=field_cache)

            updated_fields = self._update_dependencies_of_field_restored(
                field, update_collector, field_cache
            )

            ViewHandler().field_updated(updated_fields)

            if send_field_restored_signal:
                field_restored.send(
                    self, field=field, user=None, related_fields=updated_fields
                )
            update_collector.send_additional_field_updated_signals()

            for other_required_field in other_fields_that_must_restore_at_same_time:
                if other_required_field.trashed:
                    self.restore_field(other_required_field)
        except Exception as e:
            # Restoring a field could result in various errors such as a circular
            # dependency appearing in the field dep graph. Allow the field type to
            # handle any errors which occur for such situations.
            exception_handled = field_type.restore_failed(field, e)
            if exception_handled:
                field_restored.send(self, field=field, user=None, related_fields=[])
            else:
                raise e

    def _update_dependencies_of_field_restored(
        self, field, update_collector, field_cache
    ):
        FieldDependencyHandler.rebuild_dependencies([field], field_cache)

        field_type = field_type_registry.get_by_model(field)
        field_type.field_dependency_created(field, field, update_collector, field_cache)

        # Update the restored field first
        updated_fields = update_collector.apply_updates_and_get_updated_fields(
            field_cache
        )

        all_dependent_fields_grouped_by_depth = (
            FieldDependencyHandler.group_all_dependent_fields_by_level(
                field.table_id,
                [field.id],
                field_cache,
                associated_relations_changed=True,
                database_id_prefilter=field.table.database_id,
            )
        )

        for dependant_fields_group in all_dependent_fields_grouped_by_depth:
            for (
                dependant_field,
                dependant_field_type,
                path_to_starting_table,
            ) in dependant_fields_group:
                dependant_field_type.field_dependency_created(
                    dependant_field,
                    field,
                    update_collector,
                    field_cache,
                    path_to_starting_table,
                )

            updated_fields += update_collector.apply_updates_and_get_updated_fields(
                field_cache,
                skip_fields_type_changed=True,
                skip_rebuild_field_dependencies=True,
            )

        update_collector.apply_fields_type_changed(field_cache)
        update_collector.apply_rebuild_field_dependencies(field_cache)

        return updated_fields

    def move_field_between_tables(self, field_to_move, target_table):
        """
        Currently Link Row fields can have their Field instance moved between tables
        without the PK of the Field changing. This occurs when editing the link row
        field and pointing it at a new table when it was pointing at a different table
        to begin with.

        This method mainly exists to make it clearer to anyone reading the field handler
        that sometimes Field instances can literally jump tables, and any other systems
        working with fields need to handle this fact.
        """

        from .field_types import LinkRowFieldType

        field_type = field_type_registry.get_by_model(field_to_move)
        if field_type.type != LinkRowFieldType.type:
            raise NotImplementedError(
                "Can only currently move link row fields between tables."
            )

        original_table_id = field_to_move.table_id
        field_to_move.table = target_table
        field_to_move.save()
        # We are changing the related fields table so we need to invalidate
        # its old model cache as this will not happen automatically.
        invalidate_table_in_model_cache(original_table_id)
        SearchHandler.schedule_update_search_data(target_table, fields=[field_to_move])
        ViewHandler().after_field_moved_between_tables(field_to_move, original_table_id)

    def get_unique_row_values(
        self, field: Field, limit: int, split_comma_separated: bool = False
    ) -> List[str]:
        """
        Returns a list of all the unique row values for a field, sorted in order of
        frequency.

        :param field: The field whose unique values are needed.
        :param limit: The maximum number of values returned.
        :param split_comma_separated: Indicates whether the text values must be split by
            comma.
        :return: A list containing the unique values sorted by frequency.
        """

        model = field.table.get_model()
        field_object = model._field_objects[field.id]
        field_type = field_object["type"]
        field = field_object["field"]

        if not field_type.can_get_unique_values:
            raise IncompatibleFieldTypeForUniqueValues(
                f"The field type `{field_object['type']}`"
            )

        # Prepare the old value sql `p_in` to convert prepare the old value to be
        # converted to string. This is the same psql that's used when converting the
        # a field type to another type, so we're sure it's converted to the right
        # "neutral" text value.
        alter_column_prepare_old_value = field_type.get_alter_column_prepare_old_value(
            connection, field, TextField()
        )
        variables = ()

        # In some cases, the `get_alter_column_prepare_old_value` returns a tuple
        # where the first part if the psql and the second variables that must be
        # safely be injected.
        if isinstance(alter_column_prepare_old_value, tuple):
            variables = alter_column_prepare_old_value[1]
            alter_column_prepare_old_value = alter_column_prepare_old_value[0]

        # Create the temporary function try cast function. This function makes sure
        # the that if the casting fails, the query doesn't fail hard, but falls back
        # `null`.
        with connection.cursor() as cursor:
            cursor.execute(sql_drop_try_cast)
            cursor.execute(
                sql_create_try_cast
                % {
                    "alter_column_prepare_old_value": alter_column_prepare_old_value
                    or "",
                    "alter_column_prepare_new_value": "",
                    "type": "text",
                },
                variables,
            )

        # If `split_comma_separated` is `True`, then we first need to explode the raw
        # column values by comma. This means that if one of the values contains a `,
        # `, it will be treated as two values. This is for example needed when
        # converting to a multiple select field.
        if split_comma_separated:
            subselect = sql.SQL(
                """
                    select
                        trim(
                            both {trimmed} from
                            unnest(
                                regexp_split_to_array(
                                    pg_temp.try_cast({column}::text), {regex}
                                )
                            )
                        ) as col
                    from
                        {table}
                    WHERE trashed = false
                """
            ).format(
                table=sql.Identifier(model._meta.db_table),
                trimmed=sql.Literal(
                    MultipleSelectConversionConfig.trim_empty_and_quote
                ),
                column=sql.Identifier(field.db_column),
                regex=sql.Literal(MultipleSelectConversionConfig.regex_split),
            )
        # Alternatively, we just want to select the raw column value.
        else:
            subselect = sql.SQL(
                """
                SELECT pg_temp.try_cast({column}::text) as col
                FROM {table}
                WHERE trashed = false
                """
            ).format(
                table=sql.Identifier(model._meta.db_table),
                column=sql.Identifier(field.db_column),
            )

        # Finally, we executed the constructed query and return the results as a list.
        query = sql.SQL(
            """
            select col
            from ({table_select}) as tmp_table
            where col != '' and col is NOT NULL
            group by col
            order by count(col) DESC
            limit {limit}
            """
        ).format(
            table_select=subselect,
            limit=sql.Literal(limit),
        )

        with connection.cursor() as cursor:
            cursor.execute(query)
            res = cursor.fetchall()

        return [x[0] for x in res]

    def change_primary_field(
        self, user: AbstractUser, table: Table, new_primary_field: Field
    ) -> Tuple[Field, Field]:
        """
        Changes the primary field of the given table.

        :param user: The user on whose behalf the duplicated field will be
            changed.
        :param table: The table where to change the primary field in.
        :param new_primary_field: The field that must be changed to the primary field.
        :raises FieldNotInTable:
        :raises IncompatiblePrimaryFieldTypeError:
        :raises FieldIsAlreadyPrimary:
        :return: The updated field object.
        """

        if not isinstance(new_primary_field, Field):
            raise ValueError("The field is not an instance of Field.")

        if type(new_primary_field) is Field:
            raise ValueError(
                "The field must be a specific instance of Field and not the base type "
                "Field itself."
            )

        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user,
            UpdateFieldOperationType.type,
            workspace=workspace,
            context=new_primary_field,
        )

        if new_primary_field.table_id != table.id:
            raise FieldNotInTable(
                "The provided new primary field does not belong in the provided table."
            )

        new_primary_field_type = field_type_registry.get_by_model(new_primary_field)
        if not new_primary_field_type.can_be_primary_field(new_primary_field):
            raise IncompatiblePrimaryFieldTypeError(new_primary_field_type.type)

        existing_primary_fields = self.get_fields(
            table,
            Field.objects.filter(table=table, primary=True).select_for_update(),
            specific=True,
        )
        existing_primary_field = next(iter(existing_primary_fields), None)

        if existing_primary_field is None:
            raise TableHasNoPrimaryField("The provided table has no primary field.")

        if existing_primary_field.id == new_primary_field.id:
            raise FieldIsAlreadyPrimary("The provided field is already primary.")

        existing_primary_field.primary = False
        existing_primary_field.save()

        old_new_primary_field = deepcopy(new_primary_field)
        new_primary_field.primary = True
        new_primary_field.save()

        update_collector = FieldUpdateCollector(existing_primary_field.table)
        self._update_dependencies_of_field_updated(
            existing_primary_field,
            existing_primary_field,
            update_collector,
            FieldCache(),
        )

        field_updated.send(
            self,
            field=new_primary_field,
            old_field=old_new_primary_field,
            related_fields=[existing_primary_field],
            user=user,
        )

        return new_primary_field, existing_primary_field

    def _validate_name_and_optionally_rename_if_collision(
        self,
        field: Field,
        field_values: Dict[str, Any],
        postfix_for_name_collisions: Optional[str],
    ):
        """
        Validates the name of the field raising an exception if it is invalid. If the
        postfix_for_name_collisions is provided and the new name collides
        with an existing one then the provided name will be changed so it is unique
        and the update will continue. In this case the provided postfix will first be
        appended, if that is still not unique then a number will be added also.
        """

        try:
            _validate_field_name(
                field_values, field.table, field, raise_if_name_missing=False
            )
        except FieldWithSameNameAlreadyExists as e:
            if postfix_for_name_collisions is not None:
                field_values["name"] = self.find_next_unused_field_name(
                    field.table,
                    [f"{field_values['name']} {postfix_for_name_collisions}"],
                )
            else:
                raise e
