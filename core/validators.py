"""File-upload validators.

ImageField content is already verified by Pillow (rejects non-images including
SVG); these validators add an explicit extension whitelist and an upload-size
ceiling so a malicious client cannot push arbitrarily large or mislabeled
files. ``validate_document_file`` additionally constrains seller-document
uploads (the only truly arbitrary FileField) to safe document/image types.
"""

import os

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
DOCUMENT_EXTENSIONS = IMAGE_EXTENSIONS + ('.pdf', '.doc', '.docx', '.txt')
MAX_UPLOAD_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def validate_file_size(upload, max_bytes=MAX_UPLOAD_BYTES):
    if getattr(upload, 'size', None) is not None and upload.size > max_bytes:
        raise ValidationError(
            _('File must be at most %(max_mb)s MB.') % {'max_mb': max_bytes // (1024 * 1024)}
        )


def _validate_extension(name, allowed):
    ext = os.path.splitext(name or '')[1].lower()
    if ext not in allowed:
        raise ValidationError(
            _('Unsupported file type "%(ext)s". Allowed: %(allowed)s.')
            % {'ext': ext or '(none)', 'allowed': ', '.join(sorted(allowed))}
        )


def validate_image_file(upload):
    _validate_extension(getattr(upload, 'name', ''), IMAGE_EXTENSIONS)
    validate_file_size(upload)


def validate_document_file(upload):
    _validate_extension(getattr(upload, 'name', ''), DOCUMENT_EXTENSIONS)
    validate_file_size(upload)
