// Базовый JavaScript для админ-панели
document.addEventListener('DOMContentLoaded', function() {
    console.log('Admin panel loaded');
    
    // Инициализация tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
