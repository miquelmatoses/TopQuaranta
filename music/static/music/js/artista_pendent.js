(function() {
    if (window._artistaPendentInit) return;
    window._artistaPendentInit = true;

    var BASE = window.location.pathname.replace(/\/change_list\/$|$/, '').replace(/\/$/, '');

    function fetchJSON(url) {
        return fetch(url).then(function(r) { return r.json(); });
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
        // Add "Altre" option
        var altre = document.createElement('option');
        altre.value = '__altre__';
        altre.textContent = '-- Altre (text lliure) --';
        select.appendChild(altre);
    }

    function replaceWithInput(select) {
        var input = document.createElement('input');
        input.type = 'text';
        input.name = select.name;
        input.dataset.artistaId = select.dataset.artistaId;
        input.dataset.field = select.dataset.field;
        input.style.width = '150px';
        input.placeholder = 'Escriu...';
        select.parentNode.replaceChild(input, select);
    }

    function initRow(row) {
        var tSel = row.querySelector('.tq-territori');
        var cSel = row.querySelector('.tq-comarca');
        var lSel = row.querySelector('.tq-localitat');
        if (!tSel) return;

        var artistaId = tSel.dataset.artistaId;

        // Load territoris
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
            // Reset downstream
            cSel.innerHTML = '<option value="">-- Comarca --</option>';
            lSel.innerHTML = '<option value="">-- Localitat --</option>';
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
            if (!cSel.value) return;
            fetchJSON(BASE + '/municipis/municipis/?comarca=' + encodeURIComponent(cSel.value)).then(function(data) {
                populateSelect(lSel, data, '-- Localitat --');
            });
        });

        lSel.addEventListener('change', function() {
            if (lSel.value === '__altre__') {
                replaceWithInput(lSel);
            }
        });
    }

    // Inject hidden fields before form submit so Django receives the values
    function injectHiddenFields() {
        var form = document.querySelector('#changelist-form');
        if (!form) return;

        form.addEventListener('submit', function() {
            // For each artista row, write select/input values to hidden fields
            form.querySelectorAll('.tq-territori, input[data-field="territori"]').forEach(function(el) {
                var id = el.dataset.artistaId;
                var comarcaEl = form.querySelector('[data-artista-id="' + id + '"][data-field="comarca"]');
                var localitatEl = form.querySelector('[data-artista-id="' + id + '"][data-field="localitat"]');

                if (comarcaEl && comarcaEl.value && comarcaEl.value !== '__altre__') {
                    var hComarca = form.querySelector('input[name="form-' + id + '-comarca"]');
                    if (!hComarca) {
                        hComarca = document.createElement('input');
                        hComarca.type = 'hidden';
                        hComarca.name = 'pendent_comarca_' + id;
                        form.appendChild(hComarca);
                    }
                    hComarca.value = comarcaEl.value;
                }
                if (localitatEl && localitatEl.value && localitatEl.value !== '__altre__') {
                    var hLocalitat = form.querySelector('input[name="form-' + id + '-localitat"]');
                    if (!hLocalitat) {
                        hLocalitat = document.createElement('input');
                        hLocalitat.type = 'hidden';
                        hLocalitat.name = 'pendent_localitat_' + id;
                        form.appendChild(hLocalitat);
                    }
                    hLocalitat.value = localitatEl.value;
                }
            });
        });
    }

    // Init all rows
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('#result_list tbody tr').forEach(initRow);
        injectHiddenFields();
    });
})();
