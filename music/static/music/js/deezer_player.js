(function() {
    if (window._deezerPlayerInit) return;
    window._deezerPlayerInit = true;

    var currentAudio = null;
    var currentBtn = null;

    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.dz-play-btn');
        if (!btn) return;
        e.preventDefault();

        var previewUrl = btn.dataset.preview;
        if (!previewUrl) return;

        // Toggle off if same button
        if (currentBtn === btn && currentAudio) {
            currentAudio.pause();
            currentAudio = null;
            currentBtn = null;
            btn.textContent = '\u25B6';
            var existingRow = btn.closest('tr').nextElementSibling;
            if (existingRow && existingRow.classList.contains('dz-player-row')) {
                existingRow.remove();
            }
            return;
        }

        // Stop any playing audio
        if (currentAudio) {
            currentAudio.pause();
            currentBtn.textContent = '\u25B6';
            var oldRow = document.querySelector('.dz-player-row');
            if (oldRow) oldRow.remove();
        }

        // Create audio row
        var row = btn.closest('tr');
        var cols = row.querySelectorAll('td, th').length;
        var newRow = document.createElement('tr');
        newRow.className = 'dz-player-row';
        var td = document.createElement('td');
        td.colSpan = cols;
        td.style.padding = '4px 8px';
        td.style.background = '#f0f0f0';

        var audio = document.createElement('audio');
        audio.controls = true;
        audio.src = previewUrl;
        audio.style.width = '100%';
        audio.style.height = '32px';
        audio.autoplay = true;

        audio.addEventListener('ended', function() {
            btn.textContent = '\u25B6';
            currentAudio = null;
            currentBtn = null;
            newRow.remove();
        });

        td.appendChild(audio);
        newRow.appendChild(td);
        row.parentNode.insertBefore(newRow, row.nextSibling);

        currentAudio = audio;
        currentBtn = btn;
        btn.textContent = '\u25A0';
    });
})();
