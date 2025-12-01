from __future__ import annotations

import csv
import hashlib
import inspect
import io
import math
import os
import random
import re
import socket
import string
from collections import defaultdict, namedtuple
from decimal import Decimal
from fractions import Fraction
from itertools import chain, islice
from numbers import Number
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Type, Union

from django.conf import settings
from django.db import transaction
from django.db.models import ForeignKey, ManyToManyField, Model
from django.db.models.fields import NOT_PROVIDED
from django.db.transaction import get_connection

from requests.utils import guess_json_utf

from baserow.contrib.database.db.schema import optional_atomic

from .exceptions import CannotCalculateIntermediateOrder

RE_ESCAPE_CHAR = re.compile(r"\\(\\)?")
RE_PROP_NAME = re.compile(
    # Match anything that isn't a dot or bracket.
    r"[^.[\]]+"
    + "|"
    # Or match property names within brackets.
    + r"\[(?:"
    # Match a non-string expression.
    + r'([^"\'][^[]*)'
    + "|"
    # Or match strings (supports escaping characters)
    + r'(["\'])((?:(?!\\2)[^\\\\]|\\\\.)*?)\\2'
    + r")\]"
    + "|"
    # Or match "" as the space between consecutive dots or empty brackets.
    + r"(?=(?:\.|\[\])(?:\.|\[\]|$))"
)


def flatten(nested_list: List[Any]):
    """
    Efficiently deeply flatten a list.
    """

    return [
        element
        for sublist in nested_list
        for element in (flatten(sublist) if isinstance(sublist, list) else [sublist])
    ]


def split_attrs_and_m2m_fields(
    field_names: List[str], instance: Type[Model]
) -> Tuple[List[str], List[str]]:
    """
    Separates the provided field names into attributes and m2m fields. The attributes
    can be set directly on the instance using set_allowed_attrs while the m2m fields
    need to be set using the set_allowed_m2m_fields function.
    """

    attrs, m2m_fields = [], []
    for field_name in field_names:
        field = instance._meta.get_field(field_name)
        if isinstance(field, ManyToManyField):
            m2m_fields.append(field_name)
        else:
            attrs.append(field_name)
    return attrs, m2m_fields


def set_allowed_m2m_fields(values, allowed_fields, instance):
    """
    Sets the attributes of the instance with the values of the key names that are in the
    allowed_fields. The other keys are ignored. This function is specifically for
    ManyToManyFields.

    Notice that this function will make a update query to the database for each
    ManyToManyField that needs to be updated. This is because the ManyToManyField
    cannot be updated directly on the instance.
    """

    for field in allowed_fields:
        if field in values:
            getattr(instance, field).set(values[field])

    return instance


def extract_allowed(values, allowed_fields):
    """
    Returns a new dict with the values of the key names that are in the allowed_fields.
    The other keys are ignored.

    Example:
        object_1 = {
            'value_1': 'value',
            'value_2': 'value'
        }

        extract_allowed(object_1, ['value_1'])
        >> {'value_1': 'value'}

    :param values: A dict containing the values.
    :type dict:
    :param allowed_fields: A list containing the keys of the values that need to be
        extracted from the values.
    :type allowed_fields: list
    :return: The extracted values.
    :rtype: dict
    """

    allowed_values = {}
    for field in allowed_fields:
        if field in values:
            allowed_values[field] = values[field]

    return allowed_values


def set_allowed_attrs(values, allowed_fields, instance):
    """
    Sets the attributes of the instance with the values of the key names that are in the
    allowed_fields. The other keys are ignored.

    Examples:
        class Tmp(object):
            value_1 = 'value'
            value_2 = 'value'

        object_1 = {
            'value_1': 'value_2',
            'value_2': 'value_2'
        }

        tmp = set_allowed_attrs(object_1, ['value_1'], Tmp())
        tmp.value_1
        >> 'value_2'
        tmp.value_2
        >> 'value'

    :param values: The dict containing the values.
    :type values: dict
    :param allowed_fields: A list containing the keys of the value that need to be set
        on the instance.
    :type allowed_fields: list
    :param instance: The instance of which the attributes must be updated.
    :type instance: object
    :return: The updated instance.
    """

    for field in allowed_fields:
        if field in values:
            setattr(instance, field, values[field])

    return instance


def get_non_unique_values(values: List) -> List:
    """
    Assembles all values that are not unique in the provided list
    """

    unique_values = set()
    non_unique_values = set()
    for value in values:
        if value in unique_values:
            non_unique_values.add(value)
        unique_values.add(value)
    return list(non_unique_values)


def to_camel_case(value: str) -> str:
    """
    Converts the value string to camelCase.

    :param value: The value that needs to be converted.
    :return: The value in camelCase.
    """

    return (
        "".join(character for character in value.title() if not character.isspace())
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def to_pascal_case(value):
    """
    Converts the value string to PascalCase.

    :param value: The value that needs to be converted.
    :type value: str
    :return: The value in PascalCase.
    :rtype: str
    """

    return "".join(character for character in value.title() if not character.isspace())


def to_snake_case(value):
    """
    Converts the value string to snake_case.

    :param value: The value that needs to be converted.
    :type value: str
    :return: The value in snake_case.
    :rtype: str
    """

    return re.sub(" +", " ", value).lower().replace(" ", "_").strip()


def remove_special_characters(value, remove_spaces=True):
    """
    Removes all special characters from a string, so only [a-Z] and [0-9] stay.

    :param value: The value where the characters need to be removed from.
    :type value: str
    :param remove_spaces: If true the spaces are also going to be removed.
    :type remove_spaces: bool
    :return: The value in without special characters
    :rtype: str
    """

    return "".join(
        character
        for character in value
        if character.isalnum() or (character == " " and not remove_spaces)
    )


def model_default_values(model_class, not_provided=None):
    """
    Figures out which default values the fields of a model have and returns those
    as a dict.

    :param model_class: The model that contains the fields for which we need to get
        the default values.
    :type model_class: Model
    :return: A dict containing the field name as a key and the default value as value.
    :rtype: dict
    """

    return {
        field.name: (
            field.default if field.default is not NOT_PROVIDED else not_provided
        )
        for field in model_class._meta.get_fields()
        if hasattr(field, "default")
    }


def dict_to_object(values, name="Struct"):
    """
    Converts a dict to an object.

    :param values: The dict containing the values that need to be converted to an
        object.
    :type values:
    :param name: The name of the object.
    :type name: str
    :return: The object with the same attributes as the provided values.
    :rtype: object
    """

    return namedtuple(name, values.keys())(*values.values())


# This function has been adapted from js lodash stringToPath function.
# See https://github.com/lodash/lodash/blob/master/.internal/stringToPath.js
# for more information.
# The idea is to be as close as possible to the frontend version.
def to_path(path):
    """
    Generate an array of path parts from a string path.

    The function splits the input path string into individual parts,
    including attribute names and indexed access. It returns an array
    containing the path parts in the order they appear in the input path.

    Args:
        path (str): The string path to be split into parts.

    Returns:
        list: A list of path parts.

    Example:
        >>> path = 'a[0].b.c'
        >>> result = to_path(path)
        >>> print(result)
        ['a', '0', 'b', 'c']
    """

    if not path:
        return []

    result = []

    if path[0] == ".":
        result.append("")

    def replace(match):
        expression, *rest = match.groups()
        key = match.group(0)
        if expression:
            key = expression

        result.append(key.strip())

    RE_PROP_NAME.sub(replace, path)
    return result


def get_value_at_path(obj: Any, path: Union[str | List[str]], default=None) -> Any:
    """Get the value at `path` of `obj`, similar to Lodash `get` function.

    Example:
        data = {
            "a": {
                "b": {
                    "c": 123
                }
            },
            "e": [
                {"f": 1},
                {"f": 2}
            ]
        }
        get_value_at_path(data, "a.b.c")      # 123
        get_value_at_path(data, "a.e.0.f")    # 1
        get_value_at_path(data, "a.e.*.f")    # [1, 2]

    See also: https://lodash.com/docs/4.17.15#get

    :param obj: The object that holds the value
    :param path: The path to the value or a list with the path parts
    :param default: The value that must be returning if the path is not found.
    :return: The value held by the path
    """

    def _get_value_at_path(obj: Any, keys: List[str]) -> Any:
        if not keys:
            return obj
        first, *rest = keys
        if isinstance(obj, dict) and keys[0] in obj:
            return _get_value_at_path(obj[first], keys[1:])
        if isinstance(obj, list) and first.isdigit() and (key := int(first)) < len(obj):
            return _get_value_at_path(obj[key], keys[1:])
        if isinstance(obj, list) and keys[0] == "*":
            # If we're trying to extract all keys from a list, but
            # the obj is empty, then return a list. If however an
            # index is request (rest is not empty), then return None.
            if len(obj) == 0 and not rest:
                return []
            # Call recursively this function transforming the `*` in the path in a list
            # of indexes present in the object, e.g:
            # get(obj, "a.*.b") <=> [get(obj, "a.0.b"), get(obj, "a.1.b"), ...]
            results = [
                _get_value_at_path(obj, [str(index), *rest])
                for index, _ in enumerate(obj)
            ]
            # Remove empty results and return None in case there are no results
            # Note: Don't exclude false values such as booleans, empty strings, etc.
            return [result for result in results if result is not None] or None
        return default

    keys = to_path(path) if isinstance(path, str) else path
    return _get_value_at_path(obj, keys)


def random_string(length):
    """
    Generates a random string with a given length containing letters and digits.

    :param length: The amount of characters in the string.
    :type length: int
    :return: The randomly generated string
    :type: str
    """

    return "".join(
        random.SystemRandom().choice(string.ascii_letters + string.digits)
        for _ in range(length)
    )


def sha256_hash(stream, block_size=65536):
    """
    Calculates a sha256 hash for the contents of the provided stream.

    :param stream: The stream of the content where to calculate the hash for.
    :type stream: IOStream
    :param block_size: The amount of bytes that are read each time.
    :type block_size: int
    :return: The calculated hash.
    :rtype: str
    """

    stream.seek(0)
    hasher = hashlib.sha256()
    for stream_chunk in iter(lambda: stream.read(block_size), b""):
        hasher.update(stream_chunk)
    stream.seek(0)
    return hasher.hexdigest()


def stream_size(stream):
    """
    Calculates the total amount of bytes of the stream's content.

    :param stream: The stream of the content where to calculate the size for.
    :type stream: IOStream
    :return: The total size of the stream.
    :rtype: int
    """

    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    return size


def truncate_middle(content, max_length, middle="..."):
    """
    Truncates the middle part of the string if the total length if too long.

    For example:
    truncate_middle('testabcdecho', 8) == 'tes...ho'

    :param content: The string that must be truncated.
    :type: str
    :param max_length: The maximum amount of characters the string can have.
    :type max_length: int
    :param middle: The part that must be added in the middle if the provided
        content is too long.
    :type middle str
    :return: The truncated string.
    :rtype: str
    """

    if len(content) <= max_length:
        return content

    if max_length <= len(middle):
        raise ValueError(
            "The max_length cannot be lower than the length if the " "middle string."
        )

    total = max_length - len(middle)
    start = math.ceil(total / 2)
    end = math.floor(total / 2)

    left = content[:start]
    right = content[-end:] if end else ""

    return f"{left}{middle}{right}"


def split_comma_separated_string(comma_separated_string: str) -> List[str]:
    r"""
    Correctly splits a comma separated string which can contain quoted values to include
    commas in individual items like so: 'A,"B , C",D' -> ['A', 'B , C', 'D'] or using
    backslashes to escape double quotes like so: 'A,\"B,C' -> ['A', '"B', 'C'].

    :param comma_separated_string: The string to split
    :return: A list of split items from the provided string.
    """

    # Use python's csv handler as it knows how to handle quoted csv values etc.
    # csv.reader returns an iterator, we use next to get the first split row back.
    return next(
        csv.reader(
            [comma_separated_string], delimiter=",", quotechar='"', escapechar="\\"
        )
    )


def list_to_comma_separated_string(value_list: List[str]) -> str:
    """
    Converts the given list to a CSV compatible value. The result string can be parsed
    by a proper CSV parser. This function does the reverse as the previous one.

    :param value_list: List of value to convert.
    :return: A comma separated string.
    """

    out = io.StringIO()

    # Use python csv handler to convert the list to a string
    csv_writer = csv.writer(out, delimiter=",", quotechar='"', escapechar="\\")
    csv_writer.writerow(value_list)

    out.seek(0)
    result = out.read()

    # Strip removes the extra end line
    return result.strip()


def get_model_reference_field_name(lookup_model, target_model):
    """
    Figures out what the name of the field related to the `target_model` is in the
    `lookup_model`. So if the `lookup_model` has a ForeignKey pointing to the
    `target_model`, then the name of that field will be returned.

    :param lookup_model: The model that should contain the ForeignKey pointing at the
        `target_model`.
    :type lookup_model: Model
    :param target_model: The model that the ForeignKey in the `lookup_model` must be
        pointing to.
    :type target_model: Model
    :return: The name of the field.
    :rtype: str | None
    """

    # We have to loop over all the fields, check if it is a ForeignKey and check if
    # the related model is the `target_model`. We can't use isinstance to check if
    # the model is a child of View because that doesn't work with models, so we need
    # to create a tuple of parent classes and check if the `target_model` is in them.
    for field in lookup_model._meta.get_fields():
        if isinstance(field, ForeignKey) and field.related_model:
            classes = tuple(field.related_model._meta.parents.keys()) + (
                field.related_model,
            )
            if any([target_model == c for c in classes]):
                return field.name

    return None


def remove_invalid_surrogate_characters(
    content: bytes, encoding: Optional[str] = None
) -> str:
    """
    Removes illegal unicode characters from the provided content. If you for example
    run something like `b"\uD83D".encode("utf-8")`, it will result in a
    UnicodeEncodeError. This function removed the illegal characters, it keeps the
    valid emoji's.

    :param content: The content where the illegal unicode characters must be removed
        from.
    :param encoding: The coding of the provided content. Will be guessed if nothing
        is provided.
    :return: Decoded string where the unicode illegal unicode characters are removed
        from.
    """

    if encoding is None:
        encoding = guess_json_utf(content)

    return re.sub(r"\\u(d|D)([a-z|A-Z|0-9]{3})", "", content.decode(encoding, "ignore"))


def split_ending_number(name: str) -> Tuple[str, str]:
    """
    Splits a string into two parts, the first part is the string before the last
    number, the second part is the last number.

    :param string: The string to split.
    :return: A tuple with the first part and the second part.
    """

    match = re.search(r"(.+) (\d+)$", name)
    if match:
        return match.group(1), match.group(2)
    return name, ""


def find_unused_name(
    variants_to_try: Iterable[str],
    existing_names: Iterable[str],
    max_length: int = None,
    suffix: str = " {0}",
    reserved_names: Optional[Set] = None,
):
    """
    Finds an unused name among the existing names. If no names in the provided
    variants_to_try list are available then the last name in that list will
    have a number appended which ensures it is an available unique name.
    Respects the maximally allowed name length. In case the variants_to_try
    are longer than that, they will get truncated to the maximally allowed length.

    :param variants_to_try: An iterable of name variant we want to try.
    :param existing_names: An iterable of all pre existing values.
    :param max_length: Set this value if you have a length limit to the new name.
    :param suffix: The suffix you want to append to the name to avoid
      duplicate. The string is going to be formated with a number.
    :param reserved_names: Set of names that can never be used.
    :return: The first available unused name.
    """

    if reserved_names is None:
        reserved_names = set()

    existing_names_set = set(existing_names)

    if max_length is not None:
        variants_to_try = [item[0:max_length] for item in variants_to_try]

    remaining_names = set(variants_to_try) - existing_names_set
    # Some variants to try remain, let's return the first one
    if remaining_names:
        # Loop over to ensure we maintain the ordering provided by
        # variant_to_try, so we always return the first available name and
        # not any.
        for name in variants_to_try:
            if name in remaining_names and name not in reserved_names:
                return name

    # None of the names in the param list are available, now using the last one lets
    # append a number to the name until we find a free one.
    original_name = variants_to_try[-1]

    i = 2
    while True:
        suffix_to_append = suffix.format(i)
        suffix_length = len(suffix_to_append)
        length_of_original_name_with_suffix = len(original_name) + suffix_length

        # At this point we know, that the original_name can only
        # be maximally the length of max_length. Therefore
        # if the length_of_original_name_with_suffix is longer
        # we can further truncate the name by the length of the
        # suffix.
        if max_length is not None and length_of_original_name_with_suffix > max_length:
            name = f"{original_name[:-suffix_length]}{suffix_to_append}"
        else:
            name = f"{original_name}{suffix_to_append}"

        if name not in existing_names_set and name not in reserved_names:
            return name

        i += 1


def grouper(n: int, iterable: Iterable):
    """
    Groups the iterable by `n` per chunk and yields it.

    Solution from: https://stackoverflow.com/questions/8991506/iterate-an-iterator-by
    -chunks-of-n-in-python

    :param n: The amount of items per chunk.
    :param iterable: The iterable that must be grouped
    """

    it = iter(iterable)
    while True:
        chunk = tuple(islice(it, n))
        if not chunk:
            return
        yield chunk


def unique_dicts_in_list(
    list_of_dicts: List[Dict[str, any]], unique_fields: List["str"] = None
) -> Tuple[List[Dict[str, any]], List[Dict[str, any]]]:
    """
    This function provides you with a list of unique dicts within a list, and also
    tells you what dicts are duplicates.
    If you don't provide a `unique_fields` param the function will check for uniqueness
    of all the fields of the first dict.
    Please make sure that the dicts all have any field specific in `unique_fields` and
    are all the exact same structure if None is provided for `unique_fields`

    :param list_of_dicts: The list of dicts being filtered for uniqueness
    :param unique_fields: The fields which combined function as the unique constraint
    :return: The list of unique dicts and the duplicate dicts which have been filtered
        out.
    """

    if len(list_of_dicts) == 0:
        return [], []

    if unique_fields is None:
        unique_fields = list_of_dicts[0].keys()

    duplicates = []
    unique_items_map = {}
    for item in list_of_dicts:
        unique_values = []

        for unique_field in unique_fields:
            if unique_field not in item:
                raise ValueError(f"unique field {unique_field} does no exist on {item}")

            unique_values.append(item[unique_field])

        unique_values_tuple = tuple(unique_values)

        if unique_values_tuple in unique_items_map:
            duplicates.append(item)
        else:
            unique_items_map[unique_values_tuple] = item

    return list(unique_items_map.values()), duplicates


class Progress:
    """
    This helper class can be used to easily track progress of certain tasks. It's
    possible to register a child progress and reserve a range in the current progress.

    Example:
        def callback(percentage, state):
            print(f'{percentage}% {state}')

        progress = Progress(100)
        progress.register_updated_event(callback)

        for i in range(0, 10):
            sleep(0.1)
            progress.increment(state="First")

        sleep(1)
        progress.increment("Second", by=10)

        sub_progress = progress.create_child(50, 2)
        sub_progress.increment(state="Sub first")
        sleep(1)
        sub_progress.increment(state="Sub second")

        progress.increment(by=40)

    Output:
        1% First
        2% First
        3% First
        4% First
        5% First
        6% First
        8% First
        8% First
        9% First
        10% First
        20% Second
        45% Sub first
        70% Sub second
        100% None
    """

    def __init__(
        self,
        total: int,
        parent: Optional[Progress] = None,
        represents_progress: Optional[int] = None,
    ):
        """
        :param total: The total amount representing 100%. This means that the
            progress can be increment `total` times before reaching 100%.
        """

        self.total = total
        self._progress = 0
        self._last_progress = 0
        self._last_state = None
        self.updated_events = []
        self.parent = parent
        self.represents_progress = represents_progress
        self.last_parent_progress = 0

    @property
    def progress(self):
        return math.ceil(self._progress)

    def reset_with_total(self, total):
        self._progress = self._last_progress = 0
        self.total = total

    def register_updated_event(self, event):
        """
        Register another callback event. The callback is expected to have two
        parameters, one for the percentage and one for the state.

        :param event: A function that should accept the `progress` and `state`
            arguments.
        """

        self.updated_events.append(event)

    def increment(self, by: Optional[int] = 1, state: Optional[str] = None):
        """
        Increments the progress with a given amount.

        :param by: How much the progress should be increment by. If the total is
            `100` and we increment by `1`, it will add 1%, but if we increment by `10`,
            it will add 10%.
        :param state: A descriptive name of the state. This could for example be
            "Downloading files."
        """

        self.set_progress(self._progress + by, state)

    def set_progress(self, progress: int, state: Optional[str] = None):
        """
        Manually set the progress value.

        :param progress: What the new process should be. If the total is
            `100` and we set the progress to `50`, it will be 50%.
        :param state: A descriptive name of the state. This could for example be
            "Downloading files."
        """

        if self.total == 0:
            return

        new_progress = min(progress, self.total)
        new_progress_ratio = Decimal(new_progress) / self.total
        new_progress_perc = math.ceil(new_progress_ratio * 100)

        last_progress_ratio = Decimal(self._progress) / self.total
        last_progress_perc = math.ceil(last_progress_ratio * 100)

        last_progress = self._progress
        last_state = self._last_state

        self._progress = new_progress

        if self.parent is not None:
            last_parent_progress = self.last_parent_progress
            new_parent_progress = new_progress_ratio * self.represents_progress
            diff = new_parent_progress - last_parent_progress
            if diff > 0 or state != last_state:
                self.last_parent_progress = new_parent_progress
                self.parent.increment(diff, state)

        # Run all the callbacks only if something has changed.
        if new_progress_perc > last_progress_perc or state != last_state:
            self._last_progress = last_progress
            self._last_state = state
            for event in self.updated_events:
                event(new_progress_perc, state)

    def create_child(self, represents_progress: int, total: int):
        """
        Creates a child progress. Everytime the child progress increment, it will
        also update the current progress to reflect the increment.

        :param represents_progress: How much the child progress represents in this
            progress when it is at 100%. If this value would be `40` and the total is
            `100` and the child progress reaches 100%, it will increment the progress
            by 40.
        :param total: The total amount representing 100% of the child. This means
            that the progress can be increment `total` times before reaching 100%.
        """

        child_progress = Progress(
            parent=self, represents_progress=represents_progress, total=total
        )

        # If the total is 0, we can just increment the parent progress by the
        # represents progress because the child progress will never increment.
        if total == 0:
            self.increment(represents_progress)

        return child_progress

    def create_child_builder(self, represents_progress: int):
        """
        Creates a child progress. Everytime the child progress increment, it will
        also update the current progress to reflect the increment.

        :param represents_progress: How much the child progress represents in this
            progress when it is at 100%. If this value would be `40` and the total is
            `100` and the child progress reaches 100%, it will increment the progress
            by 40.
        """

        return ChildProgressBuilder(self, represents_progress)

    def track(self, represents_progress: int, state, iterable):
        child_progress = self.create_child(represents_progress, total=len(iterable))
        for i in iterable:
            yield i
            child_progress.increment(state=state)


class ChildProgressBuilder:
    def __init__(self, parent: Progress, represents_progress: int):
        self.represents_progress = represents_progress
        self.parent = parent

    @classmethod
    def build(cls, builder: Optional[ChildProgressBuilder], child_total: int):
        if builder is not None:
            parent = builder.parent
            represents_progress = builder.represents_progress
            return parent.create_child(represents_progress, child_total)
        else:
            return Progress(child_total)


class MirrorDict(defaultdict):
    """
    This dict will return the same value as the key when the value is missing.
    It can be used to replicate non existing mapping that must return the same values.

    d = MirrorDict()
    d['test'] == 'test'
    d[1] == 1
    d.get('test') == 'test'

    d['test'] = 'foo'
    d['test'] == 'foo'
    """

    def __missing__(self, key):
        return key

    def __contains__(self, key):
        return True

    def get(self, key, default=None):
        return self[key]


def atomic_if_not_already():
    """
    Returns the context manager in `optional_atomic`, passing in the `atomic`
    arg using `get_autocommit` as its value. It allows us to only call
    `transaction.atomic` if we're not already in one.
    """

    return optional_atomic(transaction.get_autocommit())


def generate_hash(value: str):
    """
    Generates a hexadecimal hash given an input value. The same function is replicated
    in the frontend as `generateHash` such that the front and backend can share the
    same hashing algorithm.
    :param value: The value used to generate the hash
    :return: The hexadecimal hash of the value provided using sha256
    """

    value_hashed = hashlib.sha256()
    value_hashed.update(str(value).encode("UTF-8"))
    return value_hashed.hexdigest()


def find_intermediate_fraction(p1: int, q1: int, p2: int, q2: int) -> Tuple[int, int]:
    """
    Find an intermediate fraction between p1/q1 and p2/q2.

    The fraction chosen is the highest fraction in the Stern-Brocot tree which falls
    strictly between the specified values. This is intended to avoid going deeper in
    the tree unnecessarily when the list is already sparse due to deletion or moving
    of items, but in fact the case when the two items are already adjacent in the tree
    is common so we shortcut it. As a bonus, this method always generates fractions
    in lowest terms, so there is no need for GCD calculations  anywhere.

    Based on `find_intermediate` in
    https://wiki.postgresql.org/wiki/User-specified_ordering_with_fractions
    """

    pl = 0
    ql = 1
    ph = 1
    qh = 0

    if p1 * q2 + 1 != p2 * q1:
        while True:
            p = pl + ph
            q = ql + qh
            if p * q1 <= q * p1:
                pl = p
                ql = q
            elif p2 * q <= q2 * p:
                ph = p
                qh = q
            else:
                return p, q
    else:
        p = p1 + p2
        q = q1 + q2

    return p, q


def find_intermediate_order(
    order_1: Union[float, Decimal],
    order_2: Union[float, Decimal],
    max_denominator: int = 10000000,
) -> float:
    """
    Calculates what the intermediate order of the two provided orders should be.
    This can be used when a row must be moved before or after another row. It just
    needs to order of the before and after row and it will return the best new order.

    - order_1
    - return_value
    - order_2

    :param order_1: The order of the before adjacent row. The new returned order will
        be after this one
    :param order_2: The order of the after adjacent row. The new returned order will
        be before this one.
    :param max_denominator: The max denominator of the fraction calculator from the
        order.
    :raises CannotCalculateIntermediateOrder: If the fractions of the orders are equal
        or if it's impossible to calculate an intermediate fraction.
    :return: The new order that can safely be used and will be a unique value.
    """

    p1, q1 = Fraction(order_1).limit_denominator(max_denominator).as_integer_ratio()
    p2, q2 = Fraction(order_2).limit_denominator(max_denominator).as_integer_ratio()

    if p1 == p2 and q1 == q2:
        raise CannotCalculateIntermediateOrder("The fractions of the orders are equal.")

    intermediate_fraction = float(Fraction(*find_intermediate_fraction(p1, q1, p2, q2)))

    if intermediate_fraction == float(order_1) or intermediate_fraction == float(
        order_2
    ):
        raise CannotCalculateIntermediateOrder(
            "Could not find an intermediate fraction because it's equal "
            "to the provided order."
        )

    return float(Fraction(*find_intermediate_fraction(p1, q1, p2, q2)))


def exception_capturer(e):
    try:
        from sentry_sdk import capture_exception

        capture_exception(e)
    except ImportError:
        pass


def transaction_on_commit_if_not_already(func):
    funcs = set(func for _, func, _ in get_connection().run_on_commit or [])
    if func not in funcs:
        transaction.on_commit(func)


def escape_csv_cell(payload):
    """
    Prevents CSV injection for a cell in a CSV file.

    Copied from: https://github.com/raphaelm/defusedcsv/blob/master/defusedcsv/csv.py.
    More about this topic: https://owasp.org/www-community/attacks/CSV_Injection
    """

    if payload is None:
        return ""
    if isinstance(payload, Number):
        return payload

    payload = str(payload)
    if (
        payload
        and payload[0] in ("@", "+", "-", "=", "|", "%")
        and not re.match("^-?[0-9,\\.]+$", payload)
    ):
        payload = payload.replace("|", "\\|")
        payload = "'" + payload
    return payload


def get_baserow_saas_base_url() -> [str, dict]:
    """
    Returns the base url of the Baserow SaaS host. In production we always want to
    connect to api.baserow.io, but in development to the saas dev env for testing
    purposes.

    :return: The base url and the headers object that must be added to the request.
    """

    base_url = "https://api.baserow.io"
    headers = {}

    if settings.DEBUG:
        base_url = "http://baserow-saas-backend:8000"
        headers["Host"] = "localhost"

    return base_url, headers


def hex_to_rgba(hex_color: str) -> tuple:
    """
    Convert a hexadecimal color to an RGBA tuple.

    :param hex_color: The color in hexadecimal format.

    :return: The color as an (R, G, B, A) tuple.
    """

    hex_color = hex_color.lstrip("#")

    if len(hex_color) == 6:
        hex_color += "ff"  # Add full opacity if alpha is not specified

    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4, 6))


def rgba_to_hex(rgba: tuple):
    """
    Convert an RGBA tuple to a hexadecimal color.

    Parameters:
    :param rgba : The color as an (R, G, B, A) tuple.

    :return: The color in hexadecimal format.
    """

    return "#{:02x}{:02x}{:02x}{:02x}".format(*rgba)


def lighten_color(hex_color: str, factor: float):
    """
    Lighten a hexadecimal color with alpha by a given factor.

    :param hex_color: The original color in hexadecimal format.
    :param factor: The factor to lighten the color by. Should be between 0 and 1.
        A factor of 0 returns the original color, while a factor of 1 returns white.

    :return:  The lightened color in hexadecimal format.
    """

    # Convert hex color to RGBA
    rgba = hex_to_rgba(hex_color)

    # Lighten the RGB part of the RGBA color
    lightened_rgb = tuple(
        int(channel + (255 - channel) * factor) for channel in rgba[:3]
    )

    # Keep the alpha channel unchanged
    alpha = rgba[3]

    # Combine the lightened RGB with the original alpha
    lightened_rgba = lightened_rgb + (alpha,)

    # Convert the lightened RGBA color back to hex
    return rgba_to_hex(lightened_rgba)


def remove_duplicates(input_list):
    """
    Removes duplicates from the input list while preserving the order of elements.

    :param input_list: List containing the items that must be deduplicated.
    """

    seen = set()
    return [x for x in input_list if not (x in seen or seen.add(x))]


def merge_dicts_no_duplicates(*dicts):
    """
    Merges multiple dictionaries by combining the lists of values for any shared keys,
    removing duplicate elements.

    Parameters:
        *dicts (dict): Multiple dictionaries with lists as values.

    Returns:
        dict: A new dictionary with merged values for shared keys, without duplicates.
    """

    merged_dict = {}

    for dictionary in dicts:
        for key in dictionary:
            # Combine the lists and remove duplicates by converting to a set,
            # then back to a list
            if key in merged_dict:
                merged_dict[key] = list(set(chain(merged_dict[key], dictionary[key])))
            else:
                merged_dict[key] = dictionary[key]

    return merged_dict


def get_all_ips(hostname: str) -> Set:
    """
    Returns a set of all IP addresses of the provided hostname.

    :param hostname: The hostname where to get the IP addresses from.
    :return: A set containing the IP addresses of the hostname.
    """

    try:
        addr_info = socket.getaddrinfo(hostname, None)
        # Extract unique IP addresses from addr_info (both IPv4 and IPv6)
        ips = {info[4][0] for info in addr_info}
        return ips
    except socket.gaierror:
        return set()


def are_hostnames_same(hostname1: str, hostname2: str) -> bool:
    """
    Resolves the IP addresses of both hostnames, and checks they resolve to the same IP
    address. In this case, `are_hostnames_same("localhost", "localhost") == True`
    because they're both resolving to the same IP.

    :param hostname1: First hostname to compare.
    :param hostname2: Second hostname to compare
    :return: True if the hostnames point to the same IP.
    """

    ips1 = get_all_ips(hostname1)
    ips2 = get_all_ips(hostname2)
    return not ips1.isdisjoint(ips2)


def are_kwargs_default(func, **kwargs):
    """Check if all provided kwargs have their default values for the given function."""

    signature = inspect.signature(func)

    for param_name, param_value in kwargs.items():
        param = signature.parameters.get(param_name)

        # Check if parameter exists and has a default
        if not param or param.default is inspect.Parameter.empty:
            return False

        # Check if the provided value matches the default
        if param_value != param.default:
            return False

    return True
