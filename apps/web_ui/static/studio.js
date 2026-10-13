/* AKB Studio: Polotno frameworkless editor wired to the pack pipeline.
   Docs: skills/polotno-sdk/SKILL.md, https://polotno.com/docs/store.md */
(function () {
  'use strict';

  var statusEl = document.getElementById('status');
  function status(text, cls) {
    statusEl.textContent = text;
    statusEl.className = cls || '';
  }

  if (typeof createPolotnoApp !== 'function') {
    document.getElementById('offline').style.display = 'block';
    status('Không tải được editor.', 'err');
    return;
  }

  var SIZES = { short: [1080, 1920], long: [1920, 1080] };
  var aspect = 'short';
  var store = null;

  function currentLayout() {
    return document.getElementById('layoutId').value;
  }
  function currentVersion() {
    return document.getElementById('packVersion').value.trim();
  }

  fetch('/api/studio/config', { cache: 'no-store' })
    .then(function (r) { return r.json(); })
    .then(function (cfg) {
      if (!cfg.hasKey) {
        var w = document.getElementById('keywarn');
        w.style.display = 'block';
        w.textContent = 'Chưa có POLOTNO_API_KEY trong .env (xin key free tại polotno.com/cabinet). ' +
          'Vẫn vẽ được nhưng file xuất có thể dính watermark.';
      }
      var app = createPolotnoApp({
        key: cfg.key || '',
        showCredit: true,
        container: document.getElementById('container'),
      });
      store = app.store;
      window.__akb = { store: store, version: 1 };
      try {
        window.polotnoConfig.setGoogleFonts(
          ['Barlow Condensed', 'Be Vietnam Pro', 'Permanent Marker']);
        window.polotnoConfig.setTextOverflow('change-font-size');
      } catch (e) { /* brand lock best-effort; starters carry locked flags */ }
      newSize('short');
      status('Sẵn sàng. Chọn layout, vẽ, rồi “Xuất PNG vào pack”.', 'ok');
    })
    .catch(function () {
      status('Không gọi được engine API.', 'err');
    });

  function newSize(kind) {
    if (!store) return;
    aspect = kind;
    var size = SIZES[kind];
    store.setSize(size[0], size[1]);
    status('Khổ ' + size[0] + '×' + size[1] + ' (' + kind + ').', 'ok');
  }

  document.getElementById('btnShort').addEventListener('click', function () { newSize('short'); });
  document.getElementById('btnLong').addEventListener('click', function () { newSize('long'); });

  function currentStarter() {
    var raw = document.getElementById('starterId').value || 'duel_columns:short';
    var parts = raw.split(':');
    return { name: parts[0], aspect: parts[1] === 'long' ? 'long' : 'short' };
  }

  document.getElementById('btnStarter').addEventListener('click', function () {
    if (!store) return;
    var starter = currentStarter();
    newSize(starter.aspect);
    var layoutEl = document.getElementById('layoutId');
    var hasLayout = false;
    for (var i = 0; i < layoutEl.options.length; i++) {
      if (layoutEl.options[i].value === starter.name) { hasLayout = true; break; }
    }
    if (hasLayout) layoutEl.value = starter.name;
    status('Đang tải mẫu ' + starter.name + ' (' + starter.aspect + ')…');
    fetch('/api/studio/starter/' + encodeURIComponent(starter.name) + '?aspect=' + starter.aspect, { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (json) {
        store.loadJSON(json);
        status('Đã nạp mẫu ' + starter.name + ' (' + starter.aspect + '). Sửa số/tên rồi xuất.', 'ok');
      })
      .catch(function () { status('Không tải được mẫu.', 'err'); });
  });

  function exportDataURL() {
    if (!store) return Promise.reject(new Error('Editor chưa sẵn sàng.'));
    status('Đang xuất PNG đúng pixel…');
    return store.waitLoading().then(function () {
      return store.toDataURL({ pixelRatio: 1, mimeType: 'image/png' });
    });
  }

  document.getElementById('btnDownload').addEventListener('click', function () {
    exportDataURL().then(function (url) {
      var a = document.createElement('a');
      a.href = url;
      a.download = aspect + '-' + currentLayout() + '.png';
      a.click();
      status('Đã tải PNG về máy.', 'ok');
    }).catch(function (e) { status(String(e && e.message || e), 'err'); });
  });

  document.getElementById('btnExport').addEventListener('click', function () {
    var btn = document.getElementById('btnExport');
    btn.disabled = true;
    exportDataURL().then(function (dataUrl) {
      return fetch('/api/studio/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version: currentVersion(),
          layout: currentLayout(),
          prefix: aspect,
          dataUrl: dataUrl,
        }),
      }).then(function (r) {
        return r.json().then(function (body) { return { ok: r.ok, body: body }; });
      });
    }).then(function (res) {
      btn.disabled = false;
      if (!res.ok) throw new Error((res.body && res.body.error) || 'Export thất bại.');
      status('Đã lưu ' + res.body.path + ' (' + res.body.width + '×' + res.body.height + ').', 'ok');
    }).catch(function (e) {
      btn.disabled = false;
      status(String(e && e.message || e), 'err');
    });
  });
})();
