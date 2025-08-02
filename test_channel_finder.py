"""
Тестовый скрипт для проверки работы ChannelFinder Enterprise Edition
"""
import asyncio
import os
from dotenv import load_dotenv
from services.channel_finder import ChannelFinder

load_dotenv()

async def test_channel_finder_advanced():
    """Тест продвинутого поиска похожих каналов"""

    # Получаем конфигурацию
    api_id = int(os.getenv("API_ID", "0"))
    api_hash = os.getenv("API_HASH", "")
    session_string = os.getenv("SESSION_STRING", "")

    if not api_id or not api_hash:
        print("❌ API_ID или API_HASH не настроены!")
        print("Получите их на https://my.telegram.org")
        return

    # Создаем экземпляр ChannelFinder с продвинутыми настройками
    finder = ChannelFinder(
        api_id,
        api_hash,
        session_string=session_string if session_string else None,
        session_name="test_session"
    )

    # Тестовые каналы (включая vcnews для сравнения с референсом)
    test_messages = [
        "https://t.me/vcnews",  # Тот же канал что в референсе
        "https://t.me/habr_com",
        "@tproger",
        "t.me/vc",
        "Найди похожие каналы для https://t.me/durov"
    ]

    print("🚀 Тестирование Enterprise ChannelFinder v2.0...\n")
    print("🎯 Особенности:")
    print("• Многоуровневый поиск (API + ключевые слова + анализ участников)")
    print("• Фильтрация по количеству подписчиков (1000+)")
    print("• Ранжирование по релевантности")
    print("• CSV экспорт")
    print("• Кэширование результатов")
    print("\n" + "=" * 70 + "\n")

    for i, message in enumerate(test_messages, 1):
        print(f"📝 Тест {i}: {message}")
        print("-" * 50)

        try:
            # Ищем похожие каналы с продвинутым алгоритмом
            results = await finder.find_similar_channels(message)

            # Выводим результаты
            formatted_result = finder.format_results_advanced(results, show_preview=10)
            print(formatted_result)

            # Показываем статистику
            if results['success']:
                print(f"📊 Статистика поиска:")
                print(f"   • Всего найдено: {results['total_found']} каналов")
                print(f"   • Методы поиска: {', '.join(results.get('search_methods_used', []))}")
                print(f"   • Фильтр подписчиков: {results.get('min_subscribers_filter', 1000):,}+")

                # Тест CSV экспорта
                if results['total_found'] > 0:
                    csv_data = finder.generate_csv_export(results)
                    csv_size = len(csv_data.getvalue())
                    print(f"   • CSV размер: {csv_size:,} байт")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 70 + "\n")

        # Пауза между запросами для соблюдения rate limits
        await asyncio.sleep(3)

    # Закрываем клиент
    await finder.close_client()
    print("✅ Тестирование завершено!")
    print("\n🎯 Сравните результаты с @simi_channels_bot для оценки качества!")


async def test_specific_channel():
    """Тест конкретного канала vcnews для сравнения с референсом"""
    api_id = int(os.getenv("API_ID", "0"))
    api_hash = os.getenv("API_HASH", "")
    session_string = os.getenv("SESSION_STRING", "")

    finder = ChannelFinder(
        api_id,
        api_hash,
        session_string=session_string if session_string else None
    )

    print("🎯 Специальный тест канала vcnews (сравнение с @simi_channels_bot)")
    print("=" * 60)

    results = await finder.find_similar_channels("https://t.me/vcnews")

    if results['success']:
        print(f"📊 Наш результат: {results['total_found']} каналов")
        print(f"📊 Референс (@simi_channels_bot): 84 канала")
        print(f"📈 Покрытие: {(results['total_found']/84)*100:.1f}%")

        print("\n🔍 Топ-10 найденных каналов:")
        for i, channel in enumerate(results['channels'][:10], 1):
            subs = channel.get('participants_count', 0)
            subs_str = f"{subs:,}" if subs > 0 else "N/A"
            print(f"{i:2d}. {channel['title'][:40]:<40} | {subs_str:>8} подписчиков")

    await finder.close_client()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "vcnews":
        asyncio.run(test_specific_channel())
    else:
        asyncio.run(test_channel_finder_advanced())
