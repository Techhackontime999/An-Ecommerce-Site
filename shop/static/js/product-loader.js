/* ═══════════════════════════════════════════════════════════════════════
   Shop-Seed — Per-Product Loading Skeleton
   -----------------------------------------------------------------------
   Shows a shimmering skeleton inside each product image area while that
   product's image is loading, then fades the real image in. Applies to
   every product card across the site (shop grids, deal cards/sliders,
   blog product cards and the product-detail stage image).

   Each skeleton stays visible for a minimum duration (MIN_MS) so the
   animation is always seen, even when the image is already cached.
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var MIN_MS = reduceMotion ? 200 : 1200; // minimum time the skeleton is visible
    var MAX_MS = reduceMotion ? 2000 : 5000; // safety net for hung/broken images
    var STAGGER_MS = reduceMotion ? 0 : 120; // cascade: reveal cards one after another
    var MAX_STAGGER = reduceMotion ? 0 : 1200; // cap so later cards don't wait forever
    var startedAt = Date.now();

    // Gate skeleton styles behind JS so no-JS users see images immediately.
    document.documentElement.classList.add('aq-img-skeleton');

    var selectors = '.product-aq-image > img, img.td-card-img, img.td-slide-img, .blog-product-card-media > img, #pdp-stage-img';
    var imgs = document.querySelectorAll(selectors);

    imgs.forEach(function (img, idx) {
        var box = img.closest('.product-aq-image, .td-card-media, .td-slide-media, .blog-product-card-media, .pdp-stage');
        if (!box) box = img.parentElement;

        var loaded = img.complete;
        var revealed = false;
        var minWait = MIN_MS + Math.min(idx * STAGGER_MS, MAX_STAGGER);

        function reveal() {
            if (revealed) return;
            revealed = true;
            img.classList.add('is-loaded');
            box.classList.remove('aq-product-loading');
        }

        // Reveal only when the image is ready AND the minimum time has passed.
        function maybeReveal() {
            if (loaded && (Date.now() - startedAt) >= minWait) reveal();
        }

        img.addEventListener('load', function () { loaded = true; maybeReveal(); });
        img.addEventListener('error', function () { loaded = true; maybeReveal(); });

        box.classList.add('aq-product-loading');

        // Enforce the minimum skeleton duration (fires even for cached images).
        setTimeout(maybeReveal, minWait);
        // Safety net so a hung or broken image never keeps its skeleton.
        setTimeout(reveal, MAX_MS);
    });
})();
