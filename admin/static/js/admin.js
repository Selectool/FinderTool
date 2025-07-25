// Базовый JavaScript для админ-панели - Улучшенная версия
document.addEventListener('DOMContentLoaded', function () {
	console.log('Admin panel loaded with enhanced UI')

	// Инициализация tooltips
	var tooltipTriggerList = [].slice.call(
		document.querySelectorAll('[data-bs-toggle="tooltip"]')
	)
	var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
		return new bootstrap.Tooltip(tooltipTriggerEl)
	})

	// Активное состояние навигации
	setActiveNavigation()

	// Плавная анимация для карточек
	animateCards()

	// Улучшенные уведомления
	initNotifications()

	// Автоматическое скрытие алертов
	autoHideAlerts()
})

// Установка активного состояния навигации
function setActiveNavigation() {
	const currentPath = window.location.pathname
	const navLinks = document.querySelectorAll('.sidebar .nav-link')

	navLinks.forEach(link => {
		const href = link.getAttribute('href')
		if (currentPath.startsWith(href) && href !== '/') {
			link.classList.add('active')
		} else if (currentPath === '/' && href === '/dashboard') {
			link.classList.add('active')
		}
	})
}

// Анимация карточек при загрузке
function animateCards() {
	const cards = document.querySelectorAll('.card')
	cards.forEach((card, index) => {
		card.style.opacity = '0'
		card.style.transform = 'translateY(20px)'

		setTimeout(() => {
			card.style.transition = 'all 0.5s ease'
			card.style.opacity = '1'
			card.style.transform = 'translateY(0)'
		}, index * 100)
	})
}

// Инициализация уведомлений
function initNotifications() {
	// Создаем контейнер для уведомлений если его нет
	if (!document.getElementById('notifications-container')) {
		const container = document.createElement('div')
		container.id = 'notifications-container'
		container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
        `
		document.body.appendChild(container)
	}
}

// Функция показа уведомлений
function showNotification(message, type = 'info', duration = 5000) {
	const container = document.getElementById('notifications-container')
	const notification = document.createElement('div')

	const typeClasses = {
		success: 'alert-success',
		error: 'alert-danger',
		warning: 'alert-warning',
		info: 'alert-info',
	}

	const icons = {
		success: 'fas fa-check-circle',
		error: 'fas fa-exclamation-circle',
		warning: 'fas fa-exclamation-triangle',
		info: 'fas fa-info-circle',
	}

	notification.className = `alert ${typeClasses[type]} alert-dismissible fade show mb-3`
	notification.style.cssText = `
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        border: none;
        border-radius: 12px;
        animation: slideInRight 0.3s ease;
    `

	notification.innerHTML = `
        <i class="${icons[type]} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `

	container.appendChild(notification)

	// Автоматическое скрытие
	if (duration > 0) {
		setTimeout(() => {
			if (notification.parentNode) {
				notification.classList.remove('show')
				setTimeout(() => {
					if (notification.parentNode) {
						notification.remove()
					}
				}, 150)
			}
		}, duration)
	}
}

// Автоматическое скрытие алертов
function autoHideAlerts() {
	const alerts = document.querySelectorAll('.alert:not(.alert-permanent)')
	alerts.forEach(alert => {
		if (!alert.querySelector('.btn-close')) {
			setTimeout(() => {
				alert.classList.remove('show')
				setTimeout(() => {
					if (alert.parentNode) {
						alert.remove()
					}
				}, 150)
			}, 5000)
		}
	})
}

// Функция для показа спиннера загрузки
function showLoadingSpinner(element) {
	const spinner = document.createElement('span')
	spinner.className = 'loading-spinner me-2'
	spinner.id = 'loading-spinner'

	if (element.querySelector('#loading-spinner')) {
		return // Спиннер уже показан
	}

	element.insertBefore(spinner, element.firstChild)
	element.disabled = true
}

// Функция для скрытия спиннера загрузки
function hideLoadingSpinner(element) {
	const spinner = element.querySelector('#loading-spinner')
	if (spinner) {
		spinner.remove()
	}
	element.disabled = false
}

// Улучшенная функция для AJAX запросов
async function makeRequest(url, options = {}) {
	const defaultOptions = {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
		},
		...options,
	}

	try {
		const response = await fetch(url, defaultOptions)
		const data = await response.json()

		if (!response.ok) {
			throw new Error(data.detail || 'Произошла ошибка')
		}

		return data
	} catch (error) {
		console.error('Request error:', error)
		showNotification(error.message, 'error')
		throw error
	}
}

// Добавляем CSS анимации
const style = document.createElement('style')
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    .fade-in {
        animation: fadeIn 0.5s ease;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
`
document.head.appendChild(style)
