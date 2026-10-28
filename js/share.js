/* CDRA share window (v1.14.15, owner request), the SECOND local script of the site (owner exception to AGENTS.md rule 8; only on the award pages).
   (v1.14.29, owner: the plaque is no longer clickable.) The share button at the right of the top bar (shown only when this script runs) opens the <dialog id="share">: the story picture (images/story/*.png),
   "Save as photo" (a plain download link, works without this script) and, only where the browser can share a picture file, "Post to Instagram Story"
   (the system share sheet, where Instagram Stories is offered). The picture is the one already on the page, copied through a canvas: no network, no storage. */
(function () {
  'use strict';
  var d = document.getElementById('share'), o = document.querySelector('.topbar-share');
  if (!d || !o || !d.showModal) return;
  var img = d.querySelector('.share-img'), b = d.querySelector('.share-ig'), note = d.querySelector('.share-note'), f = null;

  function prep() {
    if (f || b.hidden || !img.naturalWidth) return;
    var c = document.createElement('canvas');
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    c.getContext('2d').drawImage(img, 0, 0);
    c.toBlob(function (x) { if (x) f = new File([x], 'CDRA-award.png', { type: 'image/png' }); }, 'image/png');
  }
  function open() {
    d.showModal();
    if (img.complete) prep(); else img.addEventListener('load', prep, { once: true });
  }

  try {
    if (navigator.canShare && navigator.canShare({ files: [new File([''], 'a.png', { type: 'image/png' })] })) { b.hidden = false; note.hidden = true; }
  } catch (e) { /* no file sharing here: the note stays */ }

  o.hidden = false;
  o.addEventListener('click', open);
  d.addEventListener('click', function (e) { if (e.target === d) d.close(); });
  b.addEventListener('click', function () {
    if (f) navigator.share({ files: [f] }).catch(function () {});
  });
})();
