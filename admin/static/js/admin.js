// Базовый JavaScript для админ-панели - Production-ready версия
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

// Функция для получения токена из cookies
function getCookie(name) {
	const value = `; ${document.cookie}`
	const parts = value.split(`; ${name}=`)
	if (parts.length === 2) return parts.pop().split(';').shift()
	return null
}

// Улучшенная функция для AJAX запросов с аутентификацией
async function makeRequest(url, options = {}) {
	// Получаем токен из cookies (используем js_access_token который доступен для JavaScript)
	const accessToken = getCookie('js_access_token')

	// Отладочная информация о cookies
	console.log('Все cookies:', document.cookie)
	console.log('js_access_token:', accessToken)

	const defaultOptions = {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
		},
		...options,
	}

	// Добавляем токен аутентификации если он есть
	if (accessToken) {
		defaultOptions.headers['Authorization'] = `Bearer ${accessToken}`
		console.log('Токен найден и добавлен в запрос')
	} else {
		console.warn('Токен аутентификации не найден в cookies')
	}

	try {
		const response = await fetch(url, defaultOptions)

		// Проверяем статус ответа
		if (response.status === 401) {
			// Токен истек, перенаправляем на страницу входа
			console.log('Токен истек, перенаправление на логин')
			window.location.href = '/auth/login'
			return
		}

		// Проверяем Content-Type перед парсингом
		const contentType = response.headers.get('content-type')

		if (!contentType || !contentType.includes('application/json')) {
			// Если ответ не JSON, читаем как текст для отладки
			const text = await response.text()
			console.error('Получен не-JSON ответ:', text.substring(0, 200))

			if (!response.ok) {
				throw new Error(`HTTP ${response.status}: Сервер вернул не-JSON ответ`)
			}

			// Если статус OK но не JSON, возвращаем пустой объект
			return {}
		}

		const data = await response.json()

		if (!response.ok) {
			throw new Error(data.detail || data.message || `HTTP ${response.status}`)
		}

		return data
	} catch (error) {
		console.error('Request error:', error)

		// Показываем уведомление только если это не перенаправление на логин
		if (
			!error.message.includes('Failed to fetch') &&
			window.location.pathname !== '/auth/login'
		) {
			showNotification(error.message, 'error')
		}

		throw error
	}
}

// Показать детали запроса - Production-ready функция
async function showRequestDetails(requestId) {
	try {
		// Показываем индикатор загрузки
		const loadingToast = showNotification(
			'Загружаем детали запроса...',
			'info',
			2000
		)

		// Получаем детали запроса через API
		const requestData = await makeRequest(`/api/users/requests/${requestId}`)

		// Создаем модальное окно с деталями
		const modal = document.createElement('div')
		modal.className = 'modal fade'
		modal.id = 'requestDetailsModal'
		modal.setAttribute('tabindex', '-1')

		// Безопасное форматирование входных каналов
		let inputChannels = []
		try {
			inputChannels = Array.isArray(requestData.channels_input)
				? requestData.channels_input
				: JSON.parse(requestData.channels_input || '[]')
		} catch (e) {
			console.warn('Ошибка парсинга channels_input:', e)
			inputChannels = [requestData.channels_input || 'Нет данных']
		}

		// Безопасное форматирование результатов
		let results = []
		try {
			results = Array.isArray(requestData.results)
				? requestData.results
				: JSON.parse(requestData.results || '[]')
		} catch (e) {
			console.warn('Ошибка парсинга results:', e)
			results = []
		}

		// Форматируем дату
		const createdAt = new Date(requestData.created_at).toLocaleString('ru-RU')

		// Создаем HTML для входных каналов
		const inputChannelsHtml = inputChannels
			.map(
				channel =>
					`<span class="badge bg-secondary me-1 mb-1">${escapeHtml(
						channel
					)}</span>`
			)
			.join('')

		// Создаем HTML для результатов
		const resultsHtml =
			results.length > 0
				? results
						.slice(0, 10)
						.map(
							result =>
								`<div class="border rounded p-2 mb-2">
                    <strong>${escapeHtml(
											result.title || 'Без названия'
										)}</strong><br>
                    <small class="text-muted">@${escapeHtml(
											result.username || 'unknown'
										)}</small><br>
                    <small>${escapeHtml(
											result.description || 'Нет описания'
										)}</small>
                </div>`
						)
						.join('')
				: '<p class="text-muted">Результаты не найдены</p>'

		modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-search me-2"></i>
                            Детали запроса #${requestId}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6><i class="fas fa-clock me-2"></i>Время запроса</h6>
                                <p class="text-muted">${createdAt}</p>

                                <h6><i class="fas fa-user me-2"></i>Пользователь</h6>
                                <p class="text-muted">${escapeHtml(
																	requestData.user_username || 'Неизвестен'
																)}</p>
                            </div>
                            <div class="col-md-6">
                                <h6><i class="fas fa-chart-bar me-2"></i>Статистика</h6>
                                <p class="text-muted">
                                    Найдено результатов: <strong>${
																			results.length
																		}</strong><br>
                                    Входных каналов: <strong>${
																			inputChannels.length
																		}</strong>
                                </p>
                            </div>
                        </div>

                        <hr>

                        <div class="row">
                            <div class="col-12">
                                <h6><i class="fas fa-list me-2"></i>Входные каналы</h6>
                                <div class="mb-3">
                                    ${
																			inputChannelsHtml ||
																			'<span class="text-muted">Нет данных</span>'
																		}
                                </div>
                            </div>
                        </div>

                        <div class="row">
                            <div class="col-12">
                                <h6><i class="fas fa-search-plus me-2"></i>Результаты поиска</h6>
                                <div style="max-height: 300px; overflow-y: auto;">
                                    ${resultsHtml}
                                    ${
																			results.length > 10
																				? `<p class="text-muted">... и еще ${
																						results.length - 10
																				  } результатов</p>`
																				: ''
																		}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
                    </div>
                </div>
            </div>
        `

		// Добавляем модальное окно в DOM
		document.body.appendChild(modal)

		// Показываем модальное окно
		const bsModal = new bootstrap.Modal(modal)
		bsModal.show()

		// Удаляем модальное окно после закрытия
		modal.addEventListener('hidden.bs.modal', () => {
			document.body.removeChild(modal)
		})

		showNotification('Детали запроса загружены', 'success')
	} catch (error) {
		console.error('Ошибка загрузки деталей запроса:', error)
		showNotification(
			'Не удалось загрузить детали запроса: ' + error.message,
			'error'
		)
	}
}

// Функция для безопасного экранирования HTML
function escapeHtml(text) {
	if (!text) return ''
	const div = document.createElement('div')
	div.textContent = text
	return div.innerHTML
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
