/* Top Quaranta — tqcms.js */
(function(){
  // Search panel toggle
  var toggle = document.querySelector('.search-toggle');
  var panel = document.querySelector('.search-panel');
  if (toggle && panel) {
    toggle.addEventListener('click', function(){
      panel.classList.toggle('is-open');
      if (panel.classList.contains('is-open')) {
        var input = panel.querySelector('input[type="search"]');
        if (input) input.focus();
      }
    });
  }
})();
