# PMO Agent Dashboard - AI Coding Instructions

## Architecture Overview

This is a **Streamlit-based PMO (Project Management Operations) dashboard** with Azure integration. The app uses a multi-page architecture where each page is a separate Python module in the `pages/` directory.

### Key Components
- **Entry point**: `app.py` - Main dashboard with navigation grid
- **Shared utilities**: `utils.py` - Contains `render_sidebar()`, state management, and Azure Cosmos DB client
- **Page modules**: `pages/*.py` - Each page follows the pattern: import utils, call `render_sidebar()`, implement main()
- **Styling**: `style.css` - CSS variables for light/dark theme support with gradient effects

## Development Patterns

### Page Structure Convention
Every page MUST follow this exact pattern:
```python
import streamlit as st
import sys
import os
sys.path.append('..')  # Required for utils import
from utils import render_sidebar

def main():
    render_sidebar()  # ALWAYS call first - sets page config and styling
    st.header("📊 Page Title")
    # Page content here

if __name__ == "__main__":
    main()
```

### Navigation Architecture
- Main dashboard (`app.py`) uses 4+1 column grid with icon-based navigation
- Each button uses `st.switch_page()` to navigate to pages
- Sidebar navigation in `render_sidebar()` provides consistent secondary navigation
- Page links use specific icons: 🚀🏠🎯🔍📊🔧

### State Management
Use `keep_state()` utility for maintaining data across page navigation:
```python
if keep_state(uploaded_file, "uploaded_file"):
    # File exists in session state
```

## Technology Stack & Dependencies

### Core Stack (defined in pyproject.toml)
- **Streamlit 1.50.0**: Web framework
- **Pandas 2.3.3**: Data manipulation  
- **Plotly 6.3.1**: Interactive charts (use px for simple charts, go for complex)
- **OpenAI 2.3.0**: AI integration
- **Azure SDKs**: azure-ai-projects, azure-identity, azure-cosmos

### Development Workflow
```bash
# Install dependencies
uv sync

# Run development server
uv run streamlit run app.py

# Add new dependency
uv add package_name
```

## Azure Integration Patterns

### Cosmos DB Connection
Use the cached client pattern from `utils.py`:
```python
# Get container client
container_client = get_cosmos_client("container_name")

# Get database or cosmos client  
db_client = get_cosmos_client()
```

The client uses `DefaultAzureCredential` for authentication (managed identity in production, local auth in dev).

### Environment Variables Required
- `AZURE_COSMOS_ENDPOINT`
- `AZURE_COSMOS_DATABASE` 
- `OPENAI_API_KEY` (optional)

## Styling & UI Patterns

### Theme System
- Uses CSS variables for light/dark theme support
- Dark theme is default, auto-detects system preference
- Key containers use `.st-key-container{0-8}` classes for styled cards

### Common UI Components
- **Metrics**: Use `st.metric()` with delta for KPIs
- **Charts**: Plotly with consistent color scheme (blue, green, yellow, red)
- **Tabs**: Use for organizing page content (`st.tabs()`)
- **File uploads**: Always check `uploaded_file is not None` before processing

### Navigation Buttons
Main dashboard buttons require:
- Icon URL with 125px width, border-radius: 12px
- `st.button()` with `width='stretch'`
- Centered container layout using `st.columns()`

## Data Patterns

### Sample Data Structure
Pages use pandas DataFrames with realistic business data:
- Project status, team metrics, skill assessments
- Date ranges using `pd.date_range()`
- Status indicators with emojis (✅❌⚠️)

### Chart Conventions
- **Pie charts**: Use `px.pie()` with consistent color sequence
- **Bar charts**: Stack charts for skill levels (Expert/Intermediate/Beginner)  
- **Line charts**: Use `go.Scatter()` for time series with hover unified mode

## File Organization

```
├── app.py                    # Main entry point
├── utils.py                  # Shared utilities & Azure clients
├── style.css                 # Theme-aware styling
├── pages/
│   ├── 1_Dashboard_Overview.py    # KPIs and charts
│   ├── 2_Skills_Management.py     # Team skills with tabs
│   ├── 3_Document_Analysis.py     # File upload & AI analysis
│   ├── 4_Project_Monitoring.py    # Project tracking
│   └── 5_PMO_Operations.py        # Operations management
└── pyproject.toml           # Dependencies via uv
```

## Common Gotchas

1. **Always call `render_sidebar()` first** in every page - it sets page config
2. **Use `sys.path.append('..')` in page modules** to import utils
3. **Container keys must be unique** - use `st.container(key='unique_name')`  
4. **CSS targets Streamlit internals** - test styling changes across theme modes
5. **File uploads need null checks** before processing in analysis workflows

## AI Integration Notes

- Document analysis uses file upload → AI processing → structured output pattern
- Skills gap analysis simulates AI recommendations with actionable insights
- Use `st.spinner()` for AI processing feedback and `st.balloons()` for success states