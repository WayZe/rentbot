"""
Admin handlers for rentbot application.
Handles database restore functionality.
"""
import os
import logging
import asyncpg
from typing import Optional
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext

from ..config import BUTTON_DB_RESTORE, BOT_TOKEN
from ..keyboards import main_keyboard
from ..models import DatabaseStates
from ..security import admin_only
from ..services.backup_service import (
    download_and_validate_sql_dump,
    create_backup,
    restore_from_sql
)

router = Router()
logger = logging.getLogger(__name__)


def get_user_id(message: types.Message) -> int:
    """Get user ID safely from message."""
    if not message.from_user:
        raise ValueError("Message has no user")
    return message.from_user.id


def get_user_info(message: types.Message) -> tuple[int, str]:
    """Get user ID and name safely from message."""
    if not message.from_user:
        raise ValueError("Message has no user")
    full_name = message.from_user.full_name or f"User {message.from_user.id}"
    return message.from_user.id, full_name


@router.message(F.text == BUTTON_DB_RESTORE)
@admin_only
async def db_restore_button_handler(message: types.Message, state: FSMContext) -> None:
    """Handle database restore button - admin only."""
    await message.answer(
        "⚠️ <b>ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ</b>\n\n"
        "Вы собираетесь восстановить базу данных из SQL дампа.\n"
        "Перед восстановлением будет создана резервная копия текущей БД.\n\n"
        "📁 Отправьте SQL файл (дамп) для восстановления.\n"
        "Максимальный размер: 50MB",
        parse_mode="HTML",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(DatabaseStates.waiting_for_dump_file)


@router.message(DatabaseStates.waiting_for_dump_file, F.document)
@admin_only
async def handle_sql_dump_file(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """Handle receiving SQL dump file."""
    try:
        document = message.document
        if not document:
            await message.answer("❌ Документ не найден")
            return

        # Validate file
        if not document.file_name or not document.file_name.lower().endswith('.sql'):
            await message.answer("❌ Поддерживаются только файлы с расширением .sql")
            return

        if document.file_size and document.file_size > 50 * 1024 * 1024:  # 50MB
            await message.answer("❌ Размер файла превышает 50MB")
            return

        await message.answer("📥 Загружаю файл...")

        # Get file info and download
        file_info = await bot.get_file(document.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

        # Download and validate
        dump_path, error = await download_and_validate_sql_dump(file_url, document.file_name)

        if dump_path is None:
            await message.answer(error)
            return

        # Store file path in state for later use
        await state.update_data(dump_file_path=dump_path, dump_file_name=document.file_name)

        # Ask for confirmation
        file_size_kb = (document.file_size / 1024) if document.file_size else 0
        await message.answer(
            "⚠️ <b>ПОДТВЕРДИТЕ ВОССТАНОВЛЕНИЕ</b>\n\n"
            f"📁 Файл: <code>{document.file_name}</code>\n"
            f"💾 Размер: {file_size_kb:.1f} KB\n\n"
            "<b>ВНИМАНИЕ:</b>\n"
            "• Будет создана резервная копия текущей БД\n"
            "• Все данные будут заменены содержимым дампа\n"
            "• Операция необратима!\n\n"
            "Для подтверждения введите: <b>ПОДТВЕРЖДАЮ</b>",
            parse_mode="HTML"
        )
        await state.set_state(DatabaseStates.waiting_for_restore_confirmation)

    except Exception as e:
        logger.error(f"Error handling SQL dump file: {e}")
        await message.answer(f"❌ Ошибка обработки файла: {str(e)}")
        await state.clear()


@router.message(DatabaseStates.waiting_for_dump_file)
@admin_only
async def handle_wrong_dump_file(message: types.Message, state: FSMContext) -> None:
    """Handle wrong file type during dump upload."""
    await message.answer(
        "❌ Ожидается SQL файл.\n\n"
        "Пожалуйста, отправьте файл с расширением .sql"
    )


@router.message(DatabaseStates.waiting_for_restore_confirmation)
@admin_only
async def handle_restore_confirmation(message: types.Message, state: FSMContext, pool: asyncpg.Pool) -> None:
    """Handle database restore confirmation."""
    try:
        if message.text != "ПОДТВЕРЖДАЮ":
            await message.answer(
                "❌ Неверное подтверждение.\n\n"
                "Введите точно: <b>ПОДТВЕРЖДАЮ</b> (заглавными буквами)",
                parse_mode="HTML"
            )
            return

        # Get file path from state
        state_data = await state.get_data()
        dump_file_path = state_data.get('dump_file_path')
        dump_file_name = state_data.get('dump_file_name')

        if not dump_file_path or not os.path.exists(dump_file_path):
            await message.answer("❌ Файл дампа не найден. Начните процесс заново.")
            await state.clear()
            return

        await message.answer("🔄 Начинаю восстановление базы данных...")

        # Step 1: Create backup
        await message.answer("1️⃣ Создание резервной копии текущей БД...")
        backup_path, backup_error = await create_backup()

        if backup_path is None:
            await message.answer(
                f"❌ Не удалось создать резервную копию:\n{backup_error}\n\n"
                "Восстановление отменено для безопасности данных."
            )
            # Clean up dump file
            try:
                os.unlink(dump_file_path)
            except:
                pass
            await state.clear()
            return

        await message.answer(f"✅ Резервная копия создана: {os.path.basename(backup_path)}")

        # Step 2: Restore from dump
        await message.answer("2️⃣ Восстанавливаю БД из дампа...")

        # Log restore operation
        admin_id = get_user_id(message)
        logger.info(f"Starting database restore by admin {admin_id}: {dump_file_name}")

        restore_success, restore_error = await restore_from_sql(dump_file_path, pool)

        # Clean up dump file
        try:
            os.unlink(dump_file_path)
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up dump file {dump_file_path}: {cleanup_error}")

        admin_id, admin_name = get_user_info(message)

        if restore_success:
            await message.answer(
                "✅ <b>Восстановление завершено успешно!</b>\n\n"
                f"📁 Дамп: {dump_file_name}\n"
                f"💾 Резервная копия: {os.path.basename(backup_path)}\n"
                f"👤 Администратор: {admin_name} (ID: {admin_id})\n\n"
                "База данных восстановлена и готова к работе.",
                parse_mode="HTML",
                reply_markup=main_keyboard(admin_id)
            )

            logger.info(f"Database restore completed successfully by admin {admin_id}")
        else:
            await message.answer(
                f"❌ <b>Ошибка восстановления:</b>\n{restore_error}\n\n"
                f"💾 Резервная копия сохранена: {os.path.basename(backup_path)}\n"
                "Рекомендуется проверить состояние базы данных.",
                parse_mode="HTML",
                reply_markup=main_keyboard(admin_id)
            )

            logger.error(f"Database restore failed for admin {admin_id}: {restore_error}")

        await state.clear()

    except Exception as e:
        logger.error(f"Error in restore confirmation handler: {e}")
        user_id = get_user_id(message)
        await message.answer(
            f"❌ Критическая ошибка: {str(e)}\n\n"
            "Процесс восстановления прерван.",
            reply_markup=main_keyboard(user_id)
        )
        await state.clear()