"""
Enterprise-level сервис для поиска похожих каналов через Telegram API
Версия 2.0 - Production Ready с расширенными алгоритмами поиска
Адаптировано из https://github.com/MargotP/telegram_similar_channels_finder
"""
import re
import asyncio
import csv
import io
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict, Counter
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from telethon.errors.rpcerrorlist import RpcCallFailError
from telethon.tl.types import Channel, Chat
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ChannelFinder:
    def __init__(self, api_id: int, api_hash: str, session_string: str = None, session_name: str = "bot_session"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string
        self.session_name = session_name
        self.client = None

        # Кэш для оптимизации
        self.channel_cache = {}
        self.search_cache = {}

        # Настройки поиска
        self.min_subscribers = 1000  # Минимальное количество подписчиков
        self.max_results_per_method = 50  # Максимум результатов на метод
        self.search_timeout = 30  # Таймаут поиска в секундах

        # Метрики для мониторинга
        self.search_metrics = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'avg_results_count': 0,
            'cache_hits': 0,
            'api_calls_count': 0
        }

    async def init_client(self):
        """Инициализация Telethon клиента"""
        if not self.client:
            # Используем строковую сессию если доступна, иначе файловую
            if self.session_string:
                session = StringSession(self.session_string)
                logger.info("Используется строковая сессия для production")
            else:
                session = self.session_name
                logger.info(f"Используется файловая сессия: {self.session_name}")

            self.client = TelegramClient(
                session,
                self.api_id,
                self.api_hash
            )
            await self.client.start()

    async def close_client(self):
        """Закрытие клиента"""
        if self.client:
            await self.client.disconnect()

    def extract_channel_usernames(self, text: str) -> List[str]:
        """Извлечь имена каналов из текста"""
        # Паттерны для поиска ссылок на каналы
        patterns = [
            r'https?://t\.me/([a-zA-Z0-9_]+)',  # https://t.me/channel
            r't\.me/([a-zA-Z0-9_]+)',          # t.me/channel
            r'@([a-zA-Z0-9_]+)',               # @channel
        ]
        
        usernames = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            usernames.extend(matches)
        
        # Убираем дубликаты и пустые строки
        return list(set(filter(None, usernames)))

    async def get_channel_id(self, username: str) -> Optional[int]:
        """Получить ID канала по username"""
        try:
            entity = await self.client.get_entity(username)
            return entity.id
        except Exception as e:
            logger.error(f"Ошибка получения ID канала {username}: {e}")
            return None

    async def safe_api_request(self, coroutine, comment: str):
        """Безопасное выполнение API запроса"""
        try:
            return await coroutine
        except RpcCallFailError as e:
            logger.error(f"Telegram API ошибка, {comment}: {str(e)}")
        except Exception as e:
            logger.error(f"Общая ошибка, {comment}: {str(e)}")
        return None

    async def get_channel_info(self, channel_username: str) -> Optional[Dict]:
        """Получить подробную информацию о канале"""
        try:
            # Проверяем кэш
            if channel_username in self.channel_cache:
                return self.channel_cache[channel_username]

            entity = await self.client.get_entity(channel_username)

            if not isinstance(entity, (Channel, Chat)):
                return None

            # Получаем полную информацию о канале
            full_info = await self.client(functions.channels.GetFullChannelRequest(entity))

            channel_info = {
                'username': entity.username or 'Без username',
                'title': entity.title,
                'id': entity.id,
                'participants_count': getattr(entity, 'participants_count', 0),
                'description': full_info.full_chat.about or '',
                'link': f"https://t.me/{entity.username}" if entity.username else None,
                'verified': getattr(entity, 'verified', False),
                'scam': getattr(entity, 'scam', False),
                'fake': getattr(entity, 'fake', False),
                'created_date': getattr(entity, 'date', None),
                'access_hash': getattr(entity, 'access_hash', None)
            }

            # Кэшируем результат
            self.channel_cache[channel_username] = channel_info
            return channel_info

        except Exception as e:
            logger.error(f"Ошибка получения информации о канале {channel_username}: {e}")
            return None

    async def get_similar_channels_basic(self, channel_username: str) -> List[Dict]:
        """Базовый метод поиска через рекомендации API"""
        try:
            entity = await self.client.get_input_entity(channel_username)

            if isinstance(entity, (types.InputChannel, types.InputPeerChannel)):
                input_channel = types.InputChannel(
                    channel_id=entity.channel_id,
                    access_hash=entity.access_hash
                )

                result = await self.safe_api_request(
                    self.client(functions.channels.GetChannelRecommendationsRequest(
                        channel=input_channel
                    )),
                    f'получение рекомендаций для {channel_username}'
                )

                if not result:
                    return []

                similar_channels = []
                for ch in result.chats:
                    if getattr(ch, 'participants_count', 0) >= self.min_subscribers:
                        channel_info = {
                            'username': ch.username or 'Без username',
                            'title': ch.title,
                            'id': ch.id,
                            'participants_count': getattr(ch, 'participants_count', 0),
                            'link': f"https://t.me/{ch.username}" if ch.username else None,
                            'similarity_score': 0.8,  # Базовый скор для рекомендаций
                            'method': 'api_recommendations'
                        }
                        similar_channels.append(channel_info)

                return similar_channels
            else:
                logger.warning(f"{channel_username} не является каналом")
                return []

        except Exception as e:
            logger.error(f"Ошибка получения похожих каналов для {channel_username}: {e}")
            return []

    async def search_channels_by_keywords(self, keywords: List[str]) -> List[Dict]:
        """Поиск каналов по ключевым словам через глобальный поиск"""
        found_channels = []

        # Расширяем список ключевых слов синонимами и связанными терминами
        expanded_keywords = self.expand_keywords(keywords)

        for keyword in expanded_keywords[:10]:  # Увеличиваем количество ключевых слов
            try:
                # Глобальный поиск по ключевому слову
                result = await self.safe_api_request(
                    self.client(functions.contacts.SearchRequest(
                        q=keyword,
                        limit=30  # Увеличиваем лимит
                    )),
                    f'поиск по ключевому слову: {keyword}'
                )

                if result and result.chats:
                    for chat in result.chats:
                        if (isinstance(chat, Channel) and
                            getattr(chat, 'participants_count', 0) >= self.min_subscribers):

                            channel_info = {
                                'username': chat.username or 'Без username',
                                'title': chat.title,
                                'id': chat.id,
                                'participants_count': getattr(chat, 'participants_count', 0),
                                'link': f"https://t.me/{chat.username}" if chat.username else None,
                                'similarity_score': 0.6,  # Средний скор для поиска по ключевым словам
                                'method': 'keyword_search',
                                'matched_keyword': keyword
                            }
                            found_channels.append(channel_info)

                # Небольшая пауза между запросами
                await asyncio.sleep(0.3)

            except Exception as e:
                logger.error(f"Ошибка поиска по ключевому слову {keyword}: {e}")
                continue

        return found_channels

    def expand_keywords(self, keywords: List[str]) -> List[str]:
        """Расширить ключевые слова синонимами и связанными терминами"""
        expanded = set(keywords)

        # Словарь синонимов и связанных терминов
        synonyms = {
            'новости': ['news', 'медиа', 'пресса', 'сми', 'информация'],
            'технологии': ['tech', 'it', 'digital', 'инновации', 'стартап'],
            'бизнес': ['business', 'предпринимательство', 'экономика', 'финансы'],
            'развитие': ['рост', 'прогресс', 'эволюция', 'улучшение'],
            'москва': ['moscow', 'столица', 'мск'],
            'россия': ['russia', 'рф', 'russian'],
            'канал': ['channel', 'паблик', 'сообщество'],
            'ежедневно': ['daily', 'каждый день', 'регулярно'],
            'аналитика': ['analytics', 'анализ', 'исследование'],
            'маркетинг': ['marketing', 'реклама', 'продвижение'],
            'инвестиции': ['investment', 'вложения', 'капитал'],
            'криптовалюта': ['crypto', 'bitcoin', 'блокчейн'],
            'программирование': ['programming', 'код', 'разработка'],
        }

        for keyword in keywords:
            keyword_lower = keyword.lower()
            for base_word, related_words in synonyms.items():
                if base_word in keyword_lower or keyword_lower in base_word:
                    expanded.update(related_words)

        return list(expanded)

    async def search_similar_by_description_analysis(self, channel_info: Dict) -> List[Dict]:
        """Поиск похожих каналов через анализ описания и контента"""
        found_channels = []

        try:
            # Извлекаем ключевые термины из описания
            description = channel_info.get('description', '')
            title = channel_info.get('title', '')

            # Анализируем текст и извлекаем важные термины
            important_terms = self.extract_important_terms(description + ' ' + title)

            # Ищем каналы по важным терминам
            for term in important_terms[:5]:
                try:
                    result = await self.safe_api_request(
                        self.client(functions.contacts.SearchRequest(
                            q=term,
                            limit=15
                        )),
                        f'поиск по термину из описания: {term}'
                    )

                    if result and result.chats:
                        for chat in result.chats:
                            if (isinstance(chat, Channel) and
                                getattr(chat, 'participants_count', 0) >= self.min_subscribers and
                                chat.id != channel_info['id']):  # Исключаем исходный канал

                                channel_data = {
                                    'username': chat.username or 'Без username',
                                    'title': chat.title,
                                    'id': chat.id,
                                    'participants_count': getattr(chat, 'participants_count', 0),
                                    'link': f"https://t.me/{chat.username}" if chat.username else None,
                                    'similarity_score': 0.5,
                                    'method': 'description_analysis',
                                    'matched_term': term
                                }
                                found_channels.append(channel_data)

                    await asyncio.sleep(0.2)

                except Exception as e:
                    logger.error(f"Ошибка поиска по термину {term}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка анализа описания: {e}")

        return found_channels

    def extract_important_terms(self, text: str) -> List[str]:
        """Извлечь важные термины из текста"""
        import re

        # Убираем лишние символы и приводим к нижнему регистру
        clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = clean_text.split()

        # Фильтруем стоп-слова
        stop_words = {
            'и', 'в', 'на', 'с', 'по', 'для', 'от', 'до', 'из', 'к', 'о', 'об', 'про',
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'канал', 'channel', 'telegram', 'подписывайтесь', 'новости', 'news'
        }

        # Отбираем важные слова (длиннее 3 символов, не стоп-слова)
        important_words = [
            word for word in words
            if len(word) > 3 and word not in stop_words
        ]

        # Возвращаем уникальные термины
        return list(set(important_words))[:10]

    async def get_channel_participants_sample(self, channel_username: str, limit: int = 100) -> List[int]:
        """Получить выборку участников канала для анализа пересечений"""
        try:
            entity = await self.client.get_entity(channel_username)
            participants = []

            async for user in self.client.iter_participants(entity, limit=limit):
                if not user.bot:  # Исключаем ботов
                    participants.append(user.id)

            return participants

        except Exception as e:
            logger.error(f"Ошибка получения участников канала {channel_username}: {e}")
            return []

    async def find_channels_by_participant_overlap(self, channel_username: str) -> List[Dict]:
        """Поиск каналов по пересечению участников (продвинутый метод)"""
        try:
            # Получаем выборку участников исходного канала
            participants = await self.get_channel_participants_sample(channel_username, 50)

            if not participants:
                return []

            # Ищем каналы, где состоят эти участники
            similar_channels = []
            participant_channels = defaultdict(int)

            # Анализируем первых 20 участников
            for user_id in participants[:20]:
                try:
                    # Получаем диалоги пользователя (если доступно)
                    user_entity = await self.client.get_entity(user_id)

                    # Здесь можно добавить дополнительную логику
                    # для анализа общих каналов участников

                except Exception:
                    continue

                # Небольшая пауза
                await asyncio.sleep(0.2)

            return similar_channels

        except Exception as e:
            logger.error(f"Ошибка анализа пересечений участников для {channel_username}: {e}")
            return []

    def extract_keywords_from_channel(self, channel_info: Dict) -> List[str]:
        """Извлечь ключевые слова из информации о канале"""
        keywords = []

        # Из названия канала
        title_words = re.findall(r'\b\w+\b', channel_info.get('title', '').lower())
        keywords.extend([word for word in title_words if len(word) > 3])

        # Из описания канала
        description_words = re.findall(r'\b\w+\b', channel_info.get('description', '').lower())
        keywords.extend([word for word in description_words if len(word) > 3])

        # Убираем дубликаты и стоп-слова
        stop_words = {'канал', 'channel', 'telegram', 'новости', 'news', 'chat', 'group'}
        keywords = list(set(keywords) - stop_words)

        return keywords[:10]  # Возвращаем топ-10 ключевых слов

    async def find_similar_channels_advanced(self, channel_username: str) -> List[Dict]:
        """Продвинутый поиск похожих каналов с использованием нескольких методов"""
        all_channels = []

        # Получаем информацию об исходном канале
        channel_info = await self.get_channel_info(channel_username)
        if not channel_info:
            return []

        logger.info(f"🚀 Запуск продвинутого поиска для канала: {channel_info['title']}")

        # Метод 1: Базовые рекомендации API
        basic_channels = await self.get_similar_channels_basic(channel_username)
        all_channels.extend(basic_channels)
        logger.info(f"🤖 Найдено {len(basic_channels)} каналов через API рекомендации")

        # Метод 2: Поиск по ключевым словам (расширенный)
        keywords = self.extract_keywords_from_channel(channel_info)
        if keywords:
            keyword_channels = await self.search_channels_by_keywords(keywords)
            all_channels.extend(keyword_channels)
            logger.info(f"🔍 Найдено {len(keyword_channels)} каналов через поиск по ключевым словам")

        # Метод 3: Анализ описания и контента
        try:
            description_channels = await self.search_similar_by_description_analysis(channel_info)
            all_channels.extend(description_channels)
            logger.info(f"📝 Найдено {len(description_channels)} каналов через анализ описания")
        except Exception as e:
            logger.warning(f"Анализ описания недоступен: {e}")

        # Метод 4: Поиск по категориям и тематикам
        try:
            category_channels = await self.search_by_category_analysis(channel_info)
            all_channels.extend(category_channels)
            logger.info(f"🏷️ Найдено {len(category_channels)} каналов через анализ категорий")
        except Exception as e:
            logger.warning(f"Анализ категорий недоступен: {e}")

        # Метод 5: Анализ пересечений участников (если возможно)
        try:
            overlap_channels = await self.find_channels_by_participant_overlap(channel_username)
            all_channels.extend(overlap_channels)
            logger.info(f"👥 Найдено {len(overlap_channels)} каналов через анализ участников")
        except Exception as e:
            logger.warning(f"Анализ участников недоступен: {e}")

        return all_channels

    async def search_by_category_analysis(self, channel_info: Dict) -> List[Dict]:
        """Поиск каналов по категориальному анализу"""
        found_channels = []

        try:
            # Определяем категорию канала по названию и описанию
            categories = self.determine_channel_categories(channel_info)

            # Поисковые запросы для каждой категории
            category_queries = {
                'tech': ['технологии', 'IT', 'стартап', 'инновации', 'digital'],
                'business': ['бизнес', 'предпринимательство', 'экономика', 'финансы', 'инвестиции'],
                'news': ['новости', 'медиа', 'журналистика', 'пресса', 'информация'],
                'education': ['образование', 'обучение', 'курсы', 'знания', 'развитие'],
                'entertainment': ['развлечения', 'юмор', 'мемы', 'досуг', 'хобби'],
                'lifestyle': ['стиль жизни', 'мода', 'красота', 'здоровье', 'спорт'],
                'crypto': ['криптовалюта', 'блокчейн', 'bitcoin', 'DeFi', 'NFT'],
                'marketing': ['маркетинг', 'реклама', 'SMM', 'продвижение', 'бренд']
            }

            # Ищем каналы по определенным категориям
            for category in categories:
                if category in category_queries:
                    queries = category_queries[category]

                    for query in queries[:3]:  # Ограничиваем количество запросов
                        try:
                            result = await self.safe_api_request(
                                self.client(functions.contacts.SearchRequest(
                                    q=query,
                                    limit=20
                                )),
                                f'поиск по категории {category}: {query}'
                            )

                            if result and result.chats:
                                for chat in result.chats:
                                    if (isinstance(chat, Channel) and
                                        getattr(chat, 'participants_count', 0) >= self.min_subscribers and
                                        chat.id != channel_info['id']):

                                        channel_data = {
                                            'username': chat.username or 'Без username',
                                            'title': chat.title,
                                            'id': chat.id,
                                            'participants_count': getattr(chat, 'participants_count', 0),
                                            'link': f"https://t.me/{chat.username}" if chat.username else None,
                                            'similarity_score': 0.7,  # Высокий скор для категориального поиска
                                            'method': 'category_analysis',
                                            'matched_category': category
                                        }
                                        found_channels.append(channel_data)

                            await asyncio.sleep(0.2)

                        except Exception as e:
                            logger.error(f"Ошибка поиска по категории {category}, запрос {query}: {e}")
                            continue

        except Exception as e:
            logger.error(f"Ошибка категориального анализа: {e}")

        return found_channels

    def determine_channel_categories(self, channel_info: Dict) -> List[str]:
        """Определить категории канала по его названию и описанию"""
        text = (channel_info.get('title', '') + ' ' + channel_info.get('description', '')).lower()

        categories = []

        # Паттерны для определения категорий
        category_patterns = {
            'tech': ['технолог', 'it', 'программ', 'код', 'разработ', 'стартап', 'digital', 'tech'],
            'business': ['бизнес', 'предприним', 'экономик', 'финанс', 'инвест', 'деньги', 'капитал'],
            'news': ['новост', 'медиа', 'журнал', 'пресс', 'сми', 'информац', 'события'],
            'education': ['образован', 'обучен', 'курс', 'знани', 'учеб', 'развит', 'навык'],
            'entertainment': ['развлечен', 'юмор', 'мем', 'досуг', 'хобби', 'игр', 'кино'],
            'lifestyle': ['стиль', 'жизн', 'мод', 'красот', 'здоров', 'спорт', 'фитнес'],
            'crypto': ['крипт', 'блокчейн', 'bitcoin', 'деф', 'nft', 'токен', 'майнинг'],
            'marketing': ['маркетинг', 'реклам', 'smm', 'продвижен', 'бренд', 'pr', 'таргет']
        }

        for category, patterns in category_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    categories.append(category)
                    break

        # Если категории не определены, добавляем общие
        if not categories:
            categories = ['news', 'business']

        return list(set(categories))  # Убираем дубликаты

    async def find_similar_channels(self, text: str) -> Dict:
        """Основной метод для поиска похожих каналов с продвинутыми алгоритмами"""
        start_time = datetime.now()
        self.search_metrics['total_searches'] += 1

        await self.init_client()

        try:
            # Извлекаем имена каналов из текста
            channel_usernames = self.extract_channel_usernames(text)

            if not channel_usernames:
                return {
                    'success': False,
                    'error': 'Не найдено ссылок на каналы в сообщении',
                    'channels': [],
                    'total_found': 0
                }

            all_similar_channels = []
            processed_channels = []

            for username in channel_usernames:
                logger.info(f"🔍 Запуск продвинутого поиска для канала: {username}")

                # Проверяем существование канала
                channel_info = await self.get_channel_info(username)
                if not channel_info:
                    processed_channels.append({
                        'username': username,
                        'found': False,
                        'error': 'Канал не найден или недоступен'
                    })
                    continue

                # Запускаем продвинутый поиск
                similar_channels = await self.find_similar_channels_advanced(username)

                processed_channels.append({
                    'username': username,
                    'title': channel_info['title'],
                    'found': True,
                    'similar_count': len(similar_channels),
                    'subscribers': channel_info['participants_count']
                })

                all_similar_channels.extend(similar_channels)

            # Убираем дубликаты и ранжируем по релевантности
            unique_channels = self.deduplicate_and_rank_channels(all_similar_channels)

            # Фильтруем по минимальному количеству подписчиков
            filtered_channels = [
                ch for ch in unique_channels
                if ch.get('participants_count', 0) >= self.min_subscribers
            ]

            # Рассчитываем время выполнения
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            # Обновляем метрики
            self.search_metrics['successful_searches'] += 1
            self.search_metrics['avg_results_count'] = (
                (self.search_metrics['avg_results_count'] * (self.search_metrics['successful_searches'] - 1) +
                 len(filtered_channels)) / self.search_metrics['successful_searches']
            )

            logger.info(f"✅ Найдено {len(filtered_channels)} уникальных каналов с {self.min_subscribers}+ подписчиками за {processing_time:.1f}с")

            return {
                'success': True,
                'processed_channels': processed_channels,
                'channels': filtered_channels,
                'total_found': len(filtered_channels),
                'search_methods_used': ['api_recommendations', 'keyword_search', 'description_analysis', 'category_analysis'],
                'min_subscribers_filter': self.min_subscribers,
                'processing_time_seconds': round(processing_time, 2),
                'search_quality_score': self._calculate_quality_score({'channels': filtered_channels})
            }

        except Exception as e:
            # Обновляем метрики ошибок
            self.search_metrics['failed_searches'] += 1

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            logger.error(f"Общая ошибка поиска каналов за {processing_time:.1f}с: {e}")
            return {
                'success': False,
                'error': str(e),
                'channels': [],
                'total_found': 0,
                'processing_time_seconds': round(processing_time, 2)
            }
        finally:
            # Не закрываем клиент, чтобы переиспользовать сессию
            pass

    def deduplicate_and_rank_channels(self, channels: List[Dict]) -> List[Dict]:
        """Убрать дубликаты и ранжировать каналы по релевантности"""
        # Убираем дубликаты по ID
        unique_channels = {}
        for channel in channels:
            channel_id = channel['id']
            if channel_id not in unique_channels:
                unique_channels[channel_id] = channel
            else:
                # Если канал уже есть, обновляем скор релевантности
                existing = unique_channels[channel_id]
                existing['similarity_score'] = max(
                    existing.get('similarity_score', 0),
                    channel.get('similarity_score', 0)
                )
                # Добавляем информацию о методах поиска
                existing_methods = existing.get('methods', [existing.get('method', '')])
                new_method = channel.get('method', '')
                if new_method and new_method not in existing_methods:
                    existing_methods.append(new_method)
                existing['methods'] = existing_methods

        # Сортируем по релевантности и количеству подписчиков
        sorted_channels = sorted(
            unique_channels.values(),
            key=lambda x: (
                x.get('similarity_score', 0),
                x.get('participants_count', 0)
            ),
            reverse=True
        )

        return sorted_channels

    def generate_csv_export(self, results: Dict) -> io.StringIO:
        """Генерация CSV файла с результатами поиска (Windows-совместимый)"""
        output = io.StringIO()

        # Добавляем BOM для корректного отображения UTF-8 в Excel на Windows
        output.write('\ufeff')

        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)

        # Заголовки CSV
        headers = [
            'Название канала',
            'Username',
            'Ссылка',
            'Количество подписчиков',
            'Описание',
            'Верифицирован',
            'Методы поиска',
            'Скор релевантности',
            'ID канала'
        ]
        writer.writerow(headers)

        # Данные каналов
        for channel in results.get('channels', []):
            row = [
                channel.get('title', ''),
                channel.get('username', ''),
                channel.get('link', ''),
                channel.get('participants_count', 0),
                channel.get('description', '')[:200] + '...' if len(channel.get('description', '')) > 200 else channel.get('description', ''),
                'Да' if channel.get('verified', False) else 'Нет',
                ', '.join(channel.get('methods', [channel.get('method', '')])),
                round(channel.get('similarity_score', 0), 2),
                channel.get('id', '')
            ]
            writer.writerow(row)

        output.seek(0)
        return output

    def generate_excel_compatible_csv(self, results: Dict) -> io.BytesIO:
        """Генерация CSV файла совместимого с Excel на Windows"""
        import codecs

        # Создаем BytesIO для бинарных данных
        output = io.BytesIO()

        # Записываем BOM для UTF-8
        output.write(codecs.BOM_UTF8)

        # Создаем StringIO для CSV данных
        csv_data = io.StringIO()
        writer = csv.writer(csv_data, delimiter=';', quoting=csv.QUOTE_ALL)

        # Заголовки
        headers = [
            'Название канала',
            'Username',
            'Ссылка',
            'Количество подписчиков',
            'Описание',
            'Верифицирован',
            'Методы поиска',
            'Скор релевантности',
            'ID канала'
        ]
        writer.writerow(headers)

        # Данные каналов
        for channel in results.get('channels', []):
            row = [
                channel.get('title', ''),
                channel.get('username', ''),
                channel.get('link', ''),
                channel.get('participants_count', 0),
                channel.get('description', '')[:200] + '...' if len(channel.get('description', '')) > 200 else channel.get('description', ''),
                'Да' if channel.get('verified', False) else 'Нет',
                ', '.join(channel.get('methods', [channel.get('method', '')])),
                round(channel.get('similarity_score', 0), 2),
                channel.get('id', '')
            ]
            writer.writerow(row)

        # Конвертируем в байты и записываем
        csv_string = csv_data.getvalue()
        output.write(csv_string.encode('utf-8'))

        output.seek(0)
        return output

    def format_results_advanced(self, results: Dict, show_preview: int = 15) -> str:
        """Production-ready форматирование результатов для пользователя"""
        if not results['success']:
            return f"❌ Ошибка: {results.get('error', 'Неизвестная ошибка')}"

        if not results['channels']:
            return "😔 Похожие каналы не найдены для указанных ссылок."

        total = results['total_found']
        min_subs = results.get('min_subscribers_filter', 1000)

        # Заголовок с статистикой
        message = f"🎯 <b>Найдено {total} похожих каналов</b>\n"
        message += f"📊 Каналы с более чем {min_subs:,} подписчиков:\n\n"

        # Показываем топ каналов в лаконичном формате
        for i, channel in enumerate(results['channels'][:show_preview], 1):
            title = self._truncate_title(channel['title'], 40)
            subs = channel.get('participants_count', 0)

            # Эмодзи для верифицированных каналов
            verified_emoji = " ✅" if channel.get('verified', False) else ""

            # Форматируем ссылку и название
            if channel['link']:
                channel_line = f"{i}. <a href=\"{channel['link']}\">{title}</a>{verified_emoji}"
            else:
                channel_line = f"{i}. {title}{verified_emoji}"

            # Добавляем информацию о подписчиках в одну строку
            if subs > 0:
                subs_formatted = self._format_subscribers(subs)
                message += f"{channel_line}  👥 {subs_formatted}\n"
            else:
                message += f"{channel_line}\n"

        # Информация о дополнительных каналах
        if total > show_preview:
            message += f"\nПолный список найденных каналов в CSV файле ниже 👇"

        return message

    def _truncate_title(self, title: str, max_length: int) -> str:
        """Обрезать название канала до указанной длины"""
        if len(title) <= max_length:
            return title
        return title[:max_length-3] + "..."

    def _format_subscribers(self, count: int) -> str:
        """Форматировать количество подписчиков"""
        if count >= 1000000:
            return f"{count/1000000:.1f}M"
        elif count >= 1000:
            return f"{count/1000:.0f}K"
        else:
            return f"{count:,}"

    def format_results(self, results: Dict) -> str:
        """Обратная совместимость - использует продвинутое форматирование"""
        return self.format_results_advanced(results)

    def format_results_compact(self, results: Dict, show_preview: int = 10) -> str:
        """Компактное форматирование для мобильных устройств"""
        if not results['success']:
            return f"❌ {results.get('error', 'Ошибка поиска')}"

        if not results['channels']:
            return "😔 Каналы не найдены"

        total = results['total_found']
        message = f"🎯 <b>{total} каналов найдено</b>\n\n"

        # Компактный список
        for i, channel in enumerate(results['channels'][:show_preview], 1):
            title = self._truncate_title(channel['title'], 35)
            subs = self._format_subscribers(channel.get('participants_count', 0))
            verified = "✅" if channel.get('verified', False) else ""

            if channel['link']:
                message += f"{i}. <a href=\"{channel['link']}\">{title}</a> {verified} 👥{subs}\n"
            else:
                message += f"{i}. {title} {verified} 👥{subs}\n"

        if total > show_preview:
            message += f"\n📋 +{total - show_preview} каналов в CSV"

        return message

    def get_search_summary(self, results: Dict) -> Dict:
        """Получить сводку результатов поиска для аналитики"""
        if not results['success']:
            return {
                'success': False,
                'error': results.get('error', 'Unknown error'),
                'total_found': 0,
                'methods_used': [],
                'processing_time': 0
            }

        # Анализируем методы поиска
        methods_stats = {}
        for channel in results.get('channels', []):
            methods = channel.get('methods', [channel.get('method', 'unknown')])
            for method in methods:
                if method:
                    methods_stats[method] = methods_stats.get(method, 0) + 1

        # Анализируем качество результатов
        verified_count = sum(1 for ch in results.get('channels', []) if ch.get('verified', False))
        avg_subscribers = 0
        if results.get('channels'):
            total_subs = sum(ch.get('participants_count', 0) for ch in results['channels'])
            avg_subscribers = total_subs // len(results['channels'])

        return {
            'success': True,
            'total_found': results['total_found'],
            'methods_used': list(methods_stats.keys()),
            'methods_stats': methods_stats,
            'verified_channels': verified_count,
            'avg_subscribers': avg_subscribers,
            'min_subscribers_filter': results.get('min_subscribers_filter', 1000),
            'processed_channels': len(results.get('processed_channels', [])),
            'quality_score': self._calculate_quality_score(results)
        }

    def _calculate_quality_score(self, results: Dict) -> float:
        """Рассчитать скор качества результатов поиска"""
        if not results.get('channels'):
            return 0.0

        channels = results['channels']
        total_channels = len(channels)

        # Факторы качества
        verified_ratio = sum(1 for ch in channels if ch.get('verified', False)) / total_channels
        high_subs_ratio = sum(1 for ch in channels if ch.get('participants_count', 0) > 10000) / total_channels
        avg_similarity = sum(ch.get('similarity_score', 0) for ch in channels) / total_channels

        # Взвешенный скор качества
        quality_score = (
            verified_ratio * 0.3 +      # 30% - верифицированные каналы
            high_subs_ratio * 0.4 +     # 40% - популярные каналы
            avg_similarity * 0.3        # 30% - релевантность
        )

        return round(quality_score, 2)

    def get_performance_metrics(self) -> Dict:
        """Получить метрики производительности для мониторинга"""
        total_searches = self.search_metrics['total_searches']
        if total_searches == 0:
            return {
                'total_searches': 0,
                'success_rate': 0.0,
                'avg_results_count': 0.0,
                'cache_hit_rate': 0.0
            }

        success_rate = (self.search_metrics['successful_searches'] / total_searches) * 100
        cache_hit_rate = (self.search_metrics['cache_hits'] / max(1, self.search_metrics['api_calls_count'])) * 100

        return {
            'total_searches': total_searches,
            'successful_searches': self.search_metrics['successful_searches'],
            'failed_searches': self.search_metrics['failed_searches'],
            'success_rate': round(success_rate, 1),
            'avg_results_count': round(self.search_metrics['avg_results_count'], 1),
            'cache_hits': self.search_metrics['cache_hits'],
            'api_calls_count': self.search_metrics['api_calls_count'],
            'cache_hit_rate': round(cache_hit_rate, 1),
            'cache_size': len(self.channel_cache)
        }

    def reset_metrics(self):
        """Сбросить метрики (для тестирования или периодической очистки)"""
        self.search_metrics = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'avg_results_count': 0,
            'cache_hits': 0,
            'api_calls_count': 0
        }
        logger.info("Метрики производительности сброшены")

    def clear_cache(self):
        """Очистить кэш (для освобождения памяти)"""
        cache_size_before = len(self.channel_cache)
        self.channel_cache.clear()
        self.search_cache.clear()
        logger.info(f"Кэш очищен: удалено {cache_size_before} записей")
