"""
Database backup and restore service for rentbot application.
"""
import asyncio
import logging
import os
import tempfile
import aiohttp
import asyncpg
from typing import Optional, Tuple

from ..config import DB_CONFIG

logger = logging.getLogger(__name__)


async def download_and_validate_sql_dump(file_url: str, file_name: str) -> Tuple[str | None, str]:
    """
    Download and validate SQL dump file.

    Args:
        file_url: URL to download the file from
        file_name: Original filename

    Returns:
        tuple: (file_path, error_message) - file_path is None if validation failed
    """
    try:
        # Check file extension
        if not file_name.lower().endswith('.sql'):
            return None, "❌ Поддерживаются только файлы с расширением .sql"

        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='_dump.sql', prefix='rentbot_sql_')

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status != 200:
                        return None, f"❌ Не удалось загрузить файл (HTTP {response.status})"

                    # Check file size (limit: 50MB)
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > 50 * 1024 * 1024:  # 50MB
                        return None, "❌ Размер файла превышает 50MB"

                    # Download with size check
                    downloaded_size = 0
                    with open(temp_path, 'wb') as temp_file:
                        async for chunk in response.content.iter_chunked(8192):
                            downloaded_size += len(chunk)
                            if downloaded_size > 50 * 1024 * 1024:  # 50MB
                                return None, "❌ Размер файла превышает 50MB"
                            temp_file.write(chunk)

                    logger.info(f"Downloaded SQL dump: {file_name} ({downloaded_size} bytes) to {temp_path}")
                    return temp_path, ""

        except Exception as e:
            # Clean up temp file if download failed
            try:
                os.close(temp_fd)
                os.unlink(temp_path)
            except:
                pass
            raise e

    except Exception as e:
        logger.error(f"Error downloading dump file: {e}")
        return None, f"❌ Ошибка загрузки файла: {str(e)}"


async def create_backup() -> Tuple[str | None, str]:
    """
    Create a backup of the current database using pg_dump.

    Returns:
        tuple: (backup_path, error_message) - backup_path is None if backup failed
    """
    try:
        # Create temporary backup file
        temp_fd, backup_path = tempfile.mkstemp(suffix='_backup.sql', prefix='rentbot_backup_')

        try:
            # Build pg_dump command
            pg_dump_cmd = [
                'pg_dump',
                f"--host={DB_CONFIG['host']}",
                f"--port={DB_CONFIG['port']}",
                f"--username={DB_CONFIG['user']}",
                f"--dbname={DB_CONFIG['database']}",
                '--no-password',
                '--verbose',
                '--clean',
                '--if-exists',
                '--create',
                '--format=plain',
                f"--file={backup_path}"
            ]

            # Set environment variable for password
            env = os.environ.copy()
            env['PGPASSWORD'] = DB_CONFIG['password']

            # Execute pg_dump
            process = await asyncio.create_subprocess_exec(
                *pg_dump_cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                # Clean up backup file if pg_dump failed
                try:
                    os.close(temp_fd)
                    os.unlink(backup_path)
                except:
                    pass

                error_msg = stderr.decode() if stderr else "Unknown pg_dump error"
                logger.error(f"pg_dump failed: {error_msg}")
                return None, f"❌ Ошибка создания резервной копии: {error_msg}"

            # Close file descriptor (file was created by pg_dump)
            os.close(temp_fd)

            # Check if backup file exists and has content
            if not os.path.exists(backup_path) or os.path.getsize(backup_path) == 0:
                try:
                    os.unlink(backup_path)
                except:
                    pass
                return None, "❌ Резервная копия пуста или не создана"

            logger.info(f"Database backup created: {backup_path}")
            return backup_path, ""

        except Exception as e:
            # Clean up temp file if something went wrong
            try:
                os.close(temp_fd)
                os.unlink(backup_path)
            except:
                pass
            raise e

    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None, f"❌ Ошибка создания резервной копии: {str(e)}"


async def restore_from_sql(sql_dump_path: str, pool: asyncpg.Pool) -> Tuple[bool, str, Optional[asyncpg.Pool]]:
    """
    Restore database from SQL dump file using psql.

    Args:
        sql_dump_path: Path to the SQL dump file
        pool: Database connection pool

    Returns:
        tuple: (success, error_message, new_pool) - success is False if restore failed.
        new_pool should replace the old application pool whenever it is returned,
        because the old pool is closed before running psql.
    """
    new_pool: Optional[asyncpg.Pool] = None
    try:
        # Close database pool connections
        if pool:
            logger.info("Closing database connection pool...")
            await pool.close()

        # Build psql command
        psql_cmd = [
            'psql',
            f"--host={DB_CONFIG['host']}",
            f"--port={DB_CONFIG['port']}",
            f"--username={DB_CONFIG['user']}",
            f"--dbname={DB_CONFIG['database']}",
            '--no-password',
            '--quiet',
            '--file', sql_dump_path
        ]

        # Set environment variable for password
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_CONFIG['password']

        logger.info(f"Starting database restore from {sql_dump_path}")

        # Execute psql
        process = await asyncio.create_subprocess_exec(
            *psql_cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        # Re-create database pool
        logger.info("Re-creating database connection pool...")
        new_pool = await asyncpg.create_pool(**DB_CONFIG)

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown psql error"
            logger.error(f"Database restore failed: {error_msg}")
            return False, f"❌ Ошибка восстановления БД: {error_msg}", new_pool

        # Test connection to ensure database is working
        try:
            async with new_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.info("Database restore completed successfully")
            return True, "", new_pool

        except Exception as e:
            logger.error(f"Database connection test failed after restore: {e}")
            return False, f"❌ БД восстановлена, но соединение недоступно: {str(e)}", new_pool

    except Exception as e:
        logger.error(f"Error during database restore: {e}")
        return False, f"❌ Ошибка восстановления БД: {str(e)}", new_pool
