from enum import Enum


INTERNAL_TAGS = ["is_special", "template_tags", "embed", "embed_color", "embed_image", "embed_thumbnail"]

VALID_IMAGES = ["png", "webp", "gif", "jpeg", "jpg"]


class TagType(Enum):
    PLAINTEXT = 1
    HTML = 2
    DICT = 3
    LIST = 4
