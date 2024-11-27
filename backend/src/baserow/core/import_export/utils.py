from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils.encoding import force_bytes

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024


def chunk_iterator(file_obj: File, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """
    Reads a file object in chunks of a specified size.

    :param file_obj: The file object to read from.
    :param chunk_size: The size of each chunk to read. Default is 4 MB.
    :yield: Chunks of the file as bytes.
    """

    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        yield chunk


def file_chunk_generator(
    storage: Storage, file_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE
):
    """
    Generator that opens a file, reads it in chunks, and yields those chunks as bytes.
    Ensures the file remains open during iteration and closes it afterward.

    :param storage: The storage to use.
    :param file_path: The path within storage to the file to read.
    :param chunk_size: The size of each chunk to read. Default is 4 MB.

    :yield: Chunks of the file as bytes.
    """

    with storage.open(file_path, mode="rb") as file_obj:
        for chunk in chunk_iterator(file_obj, chunk_size):
            yield chunk


def chunk_generator(data: str | bytes, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """
    Generates chunks of data of a specified size.

    :param data: The data to be chunked.
    :param chunk_size: The size of each chunk. Default is 4 MB.
    :yield: Chunks of the data.
    """

    for i in range(0, len(data), chunk_size):
        yield force_bytes(data[i : i + chunk_size])
