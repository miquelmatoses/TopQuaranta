(function() {
    if (window._artistaPendentInit) return;
    window._artistaPendentInit = true;

    var BASE = window.location.pathname.replace(/\/change_list\/$|$/, '').replace(/\/$/, '');

    function fetchJSON(url) {
        return fetch(url).then(function(r) { return r.json(); });
    }

    function getCSRF() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function populateSelect(select, items, placeholder) {
        select.innerHTML = '';
        var opt = document.createElement('option');
        opt.value = '';
        opt.textContent = placeholder;
        select.appendChild(opt);
        items.forEach(function(item) {
            var o = document.createElement('option');
            if (typeof item === 'object') {
                o.value = item.codi;
                o.textContent = item.nom;
            } else {
                o.value = item;
                o.textContent = item;
            }
            select.appendChild(o);
        });
        var altre = document.createElement('option');
        altre.value = '__altre__';
        altre.textContent = '-- Altre (text lliure) --';
        select.appendChild(altre);
    }

    function replaceWithInput(select) {
        var input = document.createElement('input');
        input.type = 'text';
        input.dataset.artistaId = select.dataset.artistaId;
        input.dataset.field = select.dataset.field;
        input.className = select.className;
        input.style.width = '150px';
        input.placeholder = 'Escriu...';
        input.addEventListener('input', function() { updateAprovBtn(input.dataset.artistaId); });
        select.parentNode.replaceChild(input, select);
    }

    function getFieldValue(row, field) {
        var el = row.querySelector('[data-field="' + field + '"]');
        if (!el) return '';
        var val = el.value || '';
        return val === '__altre__' ? '' : val;
    }

    function updateAprovBtn(artistaId) {
        var row = document.querySelector('[data-artista-id="' + artistaId + '"][data-field="territori"]');
        if (!row) return;
        row = row.closest('tr');
        var btn = row.querySelector('.tq-aprovar');
        if (!btn) return;
        var t = getFieldValue(row, 'territori');
        var c = getFieldValue(row, 'comarca');
        var l = getFieldValue(row, 'localitat');
        var ready = t && c && l;
        btn.disabled = !ready;
        btn.style.opacity = ready ? '1' : '0.4';
    }

    function initRow(row) {
        var tSel = row.querySelector('.tq-territori');
        var cSel = row.querySelector('.tq-comarca');
        var lSel = row.querySelector('.tq-localitat');
        if (!tSel) return;

        var artistaId = tSel.dataset.artistaId;

        fetchJSON(BASE + '/municipis/territoris/').then(function(data) {
            populateSelect(tSel, data, '-- Territori --');
        });

        tSel.addEventListener('change', function() {
            if (tSel.value === '__altre__') {
                replaceWithInput(tSel);
                replaceWithInput(cSel);
                replaceWithInput(lSel);
                return;
            }
            cSel.innerHTML = '<option value="">-- Comarca --</option>';
            lSel.innerHTML = '<option value="">-- Localitat --</option>';
            updateAprovBtn(artistaId);
            if (!tSel.value) return;
            fetchJSON(BASE + '/municipis/comarques/?territori=' + tSel.value).then(function(data) {
                populateSelect(cSel, data, '-- Comarca --');
            });
        });

        cSel.addEventListener('change', function() {
            if (cSel.value === '__altre__') {
                replaceWithInput(cSel);
                replaceWithInput(lSel);
                return;
            }
            lSel.innerHTML = '<option value="">-- Localitat --</option>';
            updateAprovBtn(artistaId);
            if (!cSel.value) return;
            fetchJSON(BASE + '/municipis/municipis/?comarca=' + encodeURIComponent(cSel.value)).then(function(data) {
                populateSelect(lSel, data, '-- Localitat --');
            });
        });

        lSel.addEventListener('change', function() {
            if (lSel.value === '__altre__') {
                replaceWithInput(lSel);
                return;
            }
            updateAprovBtn(artistaId);
        });

        // Aprovar button
        var btnAprovar = row.querySelector('.tq-aprovar');
        if (btnAprovar) {
            btnAprovar.addEventListener('click', function() {
                var comarca = getFieldValue(row, 'comarca');
                var localitat = getFieldValue(row, 'localitat');
                if (!comarca || !localitat) {
                    alert('Cal seleccionar comarca i localitat.');
                    return;
                }
                var id = btnAprovar.dataset.id;
                fetch(BASE + '/' + id + '/aprovar/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCSRF()
                    },
                    body: JSON.stringify({comarca: comarca, localitat: localitat})
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.ok) {
                        row.style.transition = 'opacity 0.3s';
                        row.style.opacity = '0';
                        setTimeout(function() { row.remove(); }, 300);
                    } else {
                        alert('Error: ' + (data.error || 'desconegut'));
                    }
                }).catch(function(err) { alert('Error de xarxa: ' + err); });
            });
        }

        // Descartar button
        var btnDescartar = row.querySelector('.tq-descartar');
        if (btnDescartar) {
            btnDescartar.addEventListener('click', function() {
                if (!confirm('Descartar aquest artista?')) return;
                var id = btnDescartar.dataset.id;
                fetch(BASE + '/' + id + '/descartar/', {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCSRF()}
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.ok) {
                        row.style.transition = 'opacity 0.3s';
                        row.style.opacity = '0';
                        setTimeout(function() { row.remove(); }, 300);
                    } else {
                        alert('Error: ' + (data.error || 'desconegut'));
                    }
                }).catch(function(err) { alert('Error de xarxa: ' + err); });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('#result_list tbody tr').forEach(initRow);
    });
})();
