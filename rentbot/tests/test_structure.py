"""
Test package structure and file organization.
"""
import pytest
from pathlib import Path
import os


class TestPackageStructure:
    """Test the overall package structure."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def rentbot_package(self, project_root):
        """Get rentbot package directory."""
        return project_root / "rentbot"

    def test_required_files_exist(self, project_root, rentbot_package):
        """Test that all required files exist."""
        required_files = [
            # Root files
            project_root / "pyproject.toml",
            project_root / "Dockerfile",
            project_root / ".env.example",

            # Package files
            rentbot_package / "__init__.py",
            rentbot_package / "__main__.py",
            rentbot_package / "app.py",
            rentbot_package / "config.py",
            rentbot_package / "models.py",
            rentbot_package / "security.py",
            rentbot_package / "utils.py",
            rentbot_package / "keyboards.py",
            rentbot_package / "database.py",

            # Service files
            rentbot_package / "services" / "__init__.py",
            rentbot_package / "services" / "debt_service.py",
            rentbot_package / "services" / "backup_service.py",

            # Handler files
            rentbot_package / "handlers" / "__init__.py",
            rentbot_package / "handlers" / "basic_handlers.py",
            rentbot_package / "handlers" / "payment_handlers.py",
            rentbot_package / "handlers" / "admin_handlers.py",

            # Test files
            rentbot_package / "tests" / "__init__.py",
            rentbot_package / "tests" / "conftest.py",
        ]

        for file_path in required_files:
            assert file_path.exists(), f"Required file missing: {file_path}"
            assert file_path.is_file(), f"Path is not a file: {file_path}"

    def test_no_legacy_files(self, project_root):
        """Test that legacy files have been removed."""
        legacy_files = [
            project_root / "bot.py",
            project_root / "main.py",
            project_root / "run.py",
        ]

        for file_path in legacy_files:
            assert not file_path.exists(), f"Legacy file should be removed: {file_path}"

    def test_directory_structure(self, rentbot_package):
        """Test that required directories exist."""
        required_dirs = [
            rentbot_package / "services",
            rentbot_package / "handlers",
            rentbot_package / "tests",
        ]

        for dir_path in required_dirs:
            assert dir_path.exists(), f"Required directory missing: {dir_path}"
            assert dir_path.is_dir(), f"Path is not a directory: {dir_path}"

    def test_init_files_content(self, rentbot_package):
        """Test that __init__.py files have basic content."""
        # Main package init should have version info
        main_init = rentbot_package / "__init__.py"
        content = main_init.read_text()
        assert "__version__" in content
        assert "__author__" in content

        # Subpackage inits should exist and be readable
        for subdir in ["services", "handlers", "tests"]:
            init_file = rentbot_package / subdir / "__init__.py"
            assert init_file.exists()
            content = init_file.read_text()
            assert len(content.strip()) > 0  # Not empty


class TestFileContents:
    """Test that files contain expected content."""

    @pytest.fixture
    def rentbot_package(self):
        """Get rentbot package directory."""
        return Path(__file__).parent.parent

    def test_main_module_content(self, rentbot_package):
        """Test __main__.py content."""
        main_file = rentbot_package / "__main__.py"
        content = main_file.read_text()

        assert "from .app import main" in content
        assert "asyncio.run(main())" in content
        assert '__name__ == "__main__"' in content

    def test_app_module_content(self, rentbot_package):
        """Test app.py content."""
        app_file = rentbot_package / "app.py"
        content = app_file.read_text()

        assert "async def main()" in content
        assert "Bot(token=" in content
        assert "Dispatcher()" in content
        assert "start_polling" in content

    def test_config_module_content(self, rentbot_package):
        """Test config.py content."""
        config_file = rentbot_package / "config.py"
        content = config_file.read_text()

        required_constants = [
            "BOT_TOKEN",
            "ADMIN_USER_IDS",
            "DB_CONFIG",
            "DEFAULT_MONTHLY_RENT",
            "EVENT_RENT_CHARGE",
            "BUTTON_BALANCE",
        ]

        for constant in required_constants:
            assert constant in content, f"Missing constant: {constant}"

    def test_models_module_content(self, rentbot_package):
        """Test models.py content."""
        models_file = rentbot_package / "models.py"
        content = models_file.read_text()

        assert "class PaymentStates" in content
        assert "class DatabaseStates" in content
        assert "StatesGroup" in content

    def test_handlers_have_routers(self, rentbot_package):
        """Test that all handlers define routers."""
        handler_files = [
            "handlers/basic_handlers.py",
            "handlers/payment_handlers.py",
            "handlers/admin_handlers.py",
        ]

        for handler_file in handler_files:
            file_path = rentbot_package / handler_file
            content = file_path.read_text()
            assert "router = Router()" in content, f"Missing router in {handler_file}"
            assert "@router.message" in content, f"No message handlers in {handler_file}"


class TestImportStructure:
    """Test import structure and dependencies."""

    def test_relative_imports_in_package(self):
        """Test that package modules use relative imports."""
        from rentbot import config, security, utils, keyboards

        # These should import without errors
        assert config.BOT_TOKEN is not None
        assert security.is_admin is not None
        assert utils.parse_amount is not None
        assert keyboards.main_keyboard is not None

    def test_handlers_import_correctly(self):
        """Test that handlers import correctly."""
        from rentbot.handlers import basic_handlers, payment_handlers, admin_handlers

        # Each should have a router
        assert hasattr(basic_handlers, 'router')
        assert hasattr(payment_handlers, 'router')
        assert hasattr(admin_handlers, 'router')

    def test_services_import_correctly(self):
        """Test that services import correctly."""
        from rentbot.services import debt_service, backup_service

        # Key functions should be present
        assert hasattr(debt_service, 'get_balance_info')
        assert hasattr(backup_service, 'create_backup')

    def test_no_circular_imports(self):
        """Test that there are no circular import issues."""
        # This test passes if all imports succeed without ImportError
        try:
            from rentbot.app import main
            from rentbot.handlers import basic_handlers, payment_handlers, admin_handlers
            from rentbot.services import debt_service, backup_service

            # If we get here, no circular imports
            assert True
        except ImportError as e:
            pytest.fail(f"Circular import detected: {e}")


class TestDockerfile:
    """Test Dockerfile configuration."""

    @pytest.fixture
    def dockerfile_path(self):
        """Get Dockerfile path."""
        return Path(__file__).parent.parent.parent / "Dockerfile"

    def test_dockerfile_exists(self, dockerfile_path):
        """Test that Dockerfile exists."""
        assert dockerfile_path.exists()

    def test_dockerfile_uses_correct_entry_point(self, dockerfile_path):
        """Test that Dockerfile uses the correct entry point."""
        content = dockerfile_path.read_text()
        assert 'CMD ["python", "-m", "rentbot"]' in content

    def test_dockerfile_installs_postgresql_client(self, dockerfile_path):
        """Test that Dockerfile installs PostgreSQL client."""
        content = dockerfile_path.read_text()
        assert "postgresql-client" in content


class TestPyprojectToml:
    """Test pyproject.toml configuration."""

    @pytest.fixture
    def pyproject_path(self):
        """Get pyproject.toml path."""
        return Path(__file__).parent.parent.parent / "pyproject.toml"

    def test_pyproject_exists(self, pyproject_path):
        """Test that pyproject.toml exists."""
        assert pyproject_path.exists()

    def test_pyproject_has_correct_entry_point(self, pyproject_path):
        """Test that pyproject.toml has correct entry point."""
        content = pyproject_path.read_text()
        assert 'rentbot = "rentbot.app:main"' in content

    def test_pyproject_has_dependencies(self, pyproject_path):
        """Test that pyproject.toml has required dependencies."""
        content = pyproject_path.read_text()

        required_deps = [
            "aiogram",
            "apscheduler",
            "asyncpg",
            "python-dotenv",
            "aiohttp"
        ]

        for dep in required_deps:
            assert dep in content, f"Missing dependency: {dep}"