(function() {
    if (window._deezerPlayerInit) return;
    window._deezerPlayerInit = true;
    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.dz-play-btn');
        if (!btn) return;
        e.preventDefault();
        var dzId = btn.dataset.deezerId;
        var row = btn.closest('tr');
        var existing = row.nextElementSibling;
        if (existing && existing.classList.contains('dz-player-row')) {
            existing.remove();
            btn.textContent = '\u25B6';
            return;
        }
        // Remove any other open player
        document.querySelectorAll('.dz-player-row').forEach(function(el) {
            var prevBtn = el.previousElementSibling.querySelector('.dz-play-btn');
            if (prevBtn) prevBtn.textContent = '\u25B6';
            el.remove();
        });
        var cols = row.querySelectorAll('td, th').length;
        var newRow = document.createElement('tr');
        newRow.className = 'dz-player-row';
        var td = document.createElement('td');
        td.colSpan = cols;
        td.style.padding = '0';
        td.style.background = '#1a1a2e';
        td.innerHTML = '<iframe src="https://widget.deezer.com/widget/dark/track/' +
            dzId + '" width="100%" height="100" frameborder="0" ' +
            'allow="encrypted-media; clipboard-write"></iframe>';
        newRow.appendChild(td);
        row.parentNode.insertBefore(newRow, row.nextSibling);
        btn.textContent = '\u25A0';
    });
})();
