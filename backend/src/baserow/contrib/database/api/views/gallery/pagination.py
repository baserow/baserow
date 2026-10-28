from baserow.api.pagination import LimitOffsetPagination


class GalleryLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 100
