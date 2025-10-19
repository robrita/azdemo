![Dashboard Hero Banner](img/doc-extract.png)

![Dashboard Hero Banner](img/doc-analysis.png)

## 🛠️ Technology Stack

- **Frontend:** Streamlit 1.50.0 (Python-based web application framework)
- **UI Styling:** Custom CSS with Google Fonts (Gasoek One, Oswald)
- **Data Processing:** Pandas 2.3.3, Plotly 6.3.1
- **AI Integration:** Multiple Azure AI services for document extraction:
  - Azure AI Document Intelligence (Template & Neural models)
  - Azure OpenAI Vision (GPT-4.1 & GPT-5)
  - Azure Mistral Document AI
  - Azure Content Understanding
- **Visualization:** Plotly Express, Plotly Graph Objects
- **Package Management:** uv + pyproject.toml (modern Python tooling)
- **Build System:** Hatchling
- **Testing:** pytest with 100% test coverage

## 📋 Prerequisites

- Python 3.11 or higher
- uv (modern Python package installer) or pip

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/robrita/azdemo.git
cd azdemo
```

2. Install required dependencies:

### Using uv (Recommended - Modern & Fast)
```bash
uv sync
```

### Using pip (Traditional)
```bash
pip install streamlit==1.50.0 pandas==2.3.3 plotly==6.3.1 openai==2.3.0
```

3. Set up environment variables:
Create a `.env` file in the root directory (see `.env.example` for template):
```bash
# Azure Document Intelligence (Template & Neural models)
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-document-intelligence.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your-key-here
AZURE_DOCUMENT_INTELLIGENCE_TEMPLATE_MODEL=your-template-model
AZURE_DOCUMENT_INTELLIGENCE_NEURAL_MODEL=your-neural-model

# Azure OpenAI (GPT-4.1 & GPT-5 deployments)
AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-openai-api-key
AZURE_OPENAI_DEPLOYMENT_GPT4-1=gpt-4.1
AZURE_OPENAI_DEPLOYMENT_GPT5=gpt-5

# Azure Mistral Document AI
AZURE_MISTRAL_DOCUMENT_AI_ENDPOINT=https://your-mistral-endpoint/
AZURE_MISTRAL_DOCUMENT_AI_KEY=your-mistral-key

# Azure Content Understanding
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://your-content-understanding.cognitiveservices.azure.com/
AZURE_CONTENT_UNDERSTANDING_SUBSCRIPTION_KEY=your-subscription-key
AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID=your-analyzer-id
```
All services are optional. Unconfigured services will be marked as unavailable in the UI.

## 🚀 Usage

Run the Streamlit application:

### Using uv (Recommended)
```bash
uv run streamlit run app.py
```

### Using pip/system Python
```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

## 🛠️ Dependency Management

This project uses modern Python packaging standards with `pyproject.toml`:

### Core Dependencies
- **streamlit==1.50.0** - Web application framework
- **pandas==2.3.3** - Data manipulation and analysis
- **plotly==6.3.1** - Interactive visualizations
- **azure-ai-documentintelligence>=1.0.2** - Azure Document Intelligence
- **openai>=1.0.0** - Azure OpenAI integration
- **pydantic>=2.10.6** - Data validation and structured schemas
- **pymupdf>=1.26.5** - PDF to image conversion
- **python-dotenv** - Environment variable management
- **azure-identity>=1.25.1** - Azure authentication

### Key Commands with pyproject.toml

```bash
# Install all dependencies (recommended)
uv sync

# Add a new dependency
uv add package_name

# Add a development dependency
uv add --dev package_name

# Remove a dependency
uv remove package_name

# Update dependencies
uv sync --upgrade

# Run the application
uv run streamlit run app.py

# Run Python scripts
uv run python script.py

# Install from lock file (for deployment)
uv sync --frozen
```

### Why pyproject.toml + uv?

✅ **Modern Standard**: Follows PEP 518/621 Python packaging standards  
✅ **Faster**: 10-100x faster dependency resolution than pip  
✅ **Reproducible**: Lock file ensures identical environments  
✅ **Simpler**: All project configuration in one file  
✅ **Better UX**: Clear error messages and progress indicators

## 🧹 Code Quality

This project uses **Ruff** for linting and formatting - a fast, modern Python linter (like ESLint for JavaScript).

### Linting Commands

```bash
# Check for linting issues
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Check formatting without making changes
uv run ruff format --check .
```

### Ruff Configuration

All linting rules are configured in `pyproject.toml`:
- Line length: 100 characters
- Target: Python 3.11+
- Enabled rules: pycodestyle, Pyflakes, isort, pep8-naming, pyupgrade, flake8-bugbear, and more
- Auto-formatting with consistent style

### Pre-commit Checks (Recommended)

Before committing code, run:
```bash
uv run ruff check --fix .
uv run ruff format .
```

## 🧪 Testing

This project has comprehensive test coverage with pytest. Tests are organized with clear markers for unit vs integration tests.

### Quick Start - Run All Unit Tests

```bash
# Recommended: Run all unit tests
make test-unit
```

Or directly with pytest:
```bash
uv run pytest -m "not integration" -v
```

### Run Specific Test Files

```bash
# Test utilities only
uv run pytest tests/test_utils.py -v

# Test handlers only
uv run pytest tests/test_handlers.py -v

# Test schemas only
uv run pytest tests/test_schemas.py -v

# Test app integration
uv run pytest tests/test_integration.py -v
```

### Coverage Reports

Generate test coverage reports:

```bash
# Run tests with coverage
make test-cov
```

This will:
1. Run all unit tests
2. Generate coverage report in terminal
3. Create HTML coverage report in `htmlcov/` directory

View the HTML report:
```bash
# Windows
start htmlcov/index.html

# macOS
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html
```

### Common Testing Commands

```bash
# Quick test run (quiet mode)
uv run pytest -q

# Verbose output with details
uv run pytest -v

# Stop on first failure
uv run pytest -x

# Show local variables on failure
uv run pytest -l

# Run specific test
uv run pytest tests/test_handlers.py::TestDocumentIntelligenceHandler::test_extract

# Run tests matching pattern
uv run pytest -k "extract"
```

### Integration Tests

Integration tests require Azure credentials in `.env` file:

```bash
# Run integration tests (requires valid Azure credentials)
uv run pytest -m integration -v
```

### Test Organization

Tests are located in the `tests/` directory:
- `test_utils.py` - Utility function tests
- `test_handlers.py` - Service handler tests (mocked)
- `test_schemas.py` - Pydantic schema validation tests
- `test_integration.py` - End-to-end Azure service tests
- `conftest.py` - Shared pytest fixtures and configuration
- `pytest.ini` - pytest configuration

## �🧩 Makefile Workflow

For convenience, common tasks are scripted in the `Makefile`. On Windows you may need to install `make` (e.g. `choco install make`) or run these in WSL. Each target wraps the underlying `uv` commands so you don't have to remember full syntax.

### Available Targets

| Target | Purpose |
|--------|---------|
| `make help` | List all available commands |
| `make install` | Install / sync all dependencies via `uv sync` |
| `make lint` | Run Ruff lint checks (`ruff check .`) |
| `make format` | Auto-fix lint issues then format code (`ruff check --fix` + `ruff format`) |
| `make test-unit` | Run all unit tests (excludes integration tests) |
| `make test-cov` | Run tests with coverage report |
| `make run` | Start the Streamlit app (`uv run streamlit run app.py`) |
| `make check-and-run` | Lint first; if it passes, start the app |

### Usage (PowerShell / Windows)

```powershell
make help
make install
make lint
make format
make run
make check-and-run
```

If `make` is not found:

```powershell
choco install make   # Requires Chocolatey
# Or use WSL: sudo apt-get update && sudo apt-get install make
```

### Without Make

You can always run the underlying commands directly:

```powershell
uv sync
uv run ruff check .
uv run ruff check --fix .
uv run ruff format .
uv run streamlit run app.py
```

Using the Makefile ensures a consistent workflow (especially the `check-and-run` gate that prevents launching with failing lint).

## 🚀 Deployment

### Local Development
```bash
uv run streamlit run app.py
```

Access the application at `http://localhost:8501`

## 🔒 Security

- Environment variables for sensitive data (use `.env` file)
- No hardcoded credentials
- Secure file upload handling
- Input validation via Pydantic schemas

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is open source and available under the MIT License.

## 📧 Support

For support, please open an issue in the GitHub repository.

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Charts powered by [Plotly](https://plotly.com/)
- Data processing with [Pandas](https://pandas.pydata.org/)
- Icons and fonts from [Google Fonts](https://fonts.google.com/)