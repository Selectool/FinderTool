"""
Сервис для поиска похожих каналов через Telegram API
Адаптировано из https://github.com/MargotP/telegram_similar_channels_finder
"""
import re
import asyncio
from typing import List, Dict, Optional
from telethon import TelegramClient, functions, types
from telethon.errors.rpcerrorlist import RpcCallFailError
import logging

logger = logging.getLogger(__name__)


class ChannelFinder:
    def __init__(self, api_id: int, api_hash: str, session_name: str = "bot_session"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None

    async def init_client(self):
        """Инициализация Telethon клиента"""
        if not self.client:
            self.client = TelegramClient(
                self.session_name, 
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

    async def get_similar_channels(self, channel_username: str) -> Optional[List[Dict]]:
        """Найти похожие каналы для указанного канала"""
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
                    return None
                
                similar_channels = []
                for ch in result.chats:
                    channel_info = {
                        'username': ch.username or 'Без username',
                        'title': ch.title,
                        'id': ch.id,
                        'participants_count': getattr(ch, 'participants_count', 0),
                        'link': f"https://t.me/{ch.username}" if ch.username else None
                    }
                    similar_channels.append(channel_info)
                
                return similar_channels
            else:
                logger.warning(f"{channel_username} не является каналом")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения похожих каналов для {channel_username}: {e}")
            return None

    async def find_similar_channels(self, text: str) -> Dict:
        """Основной метод для поиска похожих каналов"""
        await self.init_client()
        
        try:
            # Извлекаем имена каналов из текста
            channel_usernames = self.extract_channel_usernames(text)
            
            if not channel_usernames:
                return {
                    'success': False,
                    'error': 'Не найдено ссылок на каналы в сообщении',
                    'channels': []
                }
            
            all_similar_channels = []
            processed_channels = []
            
            for username in channel_usernames:
                logger.info(f"Обрабатываем канал: {username}")
                
                # Получаем ID канала
                channel_id = await self.get_channel_id(username)
                if channel_id is None:
                    processed_channels.append({
                        'username': username,
                        'found': False,
                        'error': 'Канал не найден'
                    })
                    continue
                
                # Ищем похожие каналы
                similar_channels = await self.get_similar_channels(username)
                
                if similar_channels:
                    processed_channels.append({
                        'username': username,
                        'found': True,
                        'similar_count': len(similar_channels)
                    })
                    all_similar_channels.extend(similar_channels)
                else:
                    processed_channels.append({
                        'username': username,
                        'found': True,
                        'similar_count': 0
                    })
            
            # Убираем дубликаты по ID
            unique_channels = {}
            for channel in all_similar_channels:
                if channel['id'] not in unique_channels:
                    unique_channels[channel['id']] = channel
            
            return {
                'success': True,
                'processed_channels': processed_channels,
                'channels': list(unique_channels.values()),
                'total_found': len(unique_channels)
            }
            
        except Exception as e:
            logger.error(f"Общая ошибка поиска каналов: {e}")
            return {
                'success': False,
                'error': str(e),
                'channels': []
            }
        finally:
            # Не закрываем клиент, чтобы переиспользовать сессию
            pass

    def format_results(self, results: Dict) -> str:
        """Форматировать результаты для отправки пользователю"""
        if not results['success']:
            return f"❌ Ошибка: {results.get('error', 'Неизвестная ошибка')}"
        
        if not results['channels']:
            return "😔 Похожие каналы не найдены для указанных ссылок."
        
        message = f"🔍 <b>Найдено {results['total_found']} похожих каналов:</b>\n\n"
        
        for i, channel in enumerate(results['channels'][:20], 1):  # Ограничиваем 20 каналами
            title = channel['title'][:50] + "..." if len(channel['title']) > 50 else channel['title']
            
            if channel['link']:
                message += f"{i}. <a href=\"{channel['link']}\">{title}</a>\n"
            else:
                message += f"{i}. {title} (ID: {channel['id']})\n"
            
            if channel['participants_count'] > 0:
                message += f"   👥 {channel['participants_count']} участников\n"
            message += "\n"
        
        if len(results['channels']) > 20:
            message += f"... и еще {len(results['channels']) - 20} каналов\n"
        
        return message
