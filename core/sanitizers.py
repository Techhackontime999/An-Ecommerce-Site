"""HTML sanitization for user- and staff-authored rich text.

All RichTextField content that reaches templates is rendered through
``sanitize_html`` (via the ``|richtext`` template filter) so an attacker who
plants a ``<script>`` or ``onerror=`` payload in a product description, blog
post, FAQ answer, etc. cannot execute JavaScript on visitors. This is the
primary defence against stored XSS.
"""

import bleach

# Keep the rich-text features CKEditor actually produces. No event handlers,
# no scripts, no iframes/objects/embeds, no <style> blocks.
ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'em', 'h1', 'h2',
    'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 's',
    'span', 'strike', 'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'th',
    'thead', 'tr', 'u', 'ul',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'abbr': ['title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
}

# Only these URL protocols are permitted on href/src. Notably excludes
# ``data:`` (which HTML5 browsers treat as opaque in <a href> and which some
# older parsers mishandle on <img src>).
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'tel']


def sanitize_html(html):
    """Return ``html`` with executable/injection payloads stripped.

    Keeps the CKEditor feature set (tables, images, links, lists, headings)
    while removing scripts, event handlers, ``javascript:`` URLs, ``<style>``,
    ``<iframe>`` and other dangerous constructs. Safe to run on already-clean
    content (idempotent).
    """
    if not html:
        return html

    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
