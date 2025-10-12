# PMO Agent Dashboard

A comprehensive Project Management Operations (PMO) platform built with Streamlit to automate and enhance project management workflows. The platform provides four specialized AI-powered modules designed to streamline PMO operations, from skills management to document analysis and project monitoring.

## 🚀 Features

### Four Specialized AI-Powered Modules

1. **👥 Skills Management**
   - Track team skills and proficiencies
   - AI-powered skills gap analysis
   - Automated training recommendations
   - Skills distribution visualization

2. **📄 Document Analysis**
   - Intelligent document processing
   - AI-powered summary generation
   - Risk identification
   - Compliance checking
   - Action items extraction

3. **📊 Project Monitoring**
   - Real-time project dashboards
   - Timeline and Gantt visualization
   - Budget tracking and allocation
   - Progress monitoring
   - Status reporting

4. **🔧 PMO Operations**
   - Resource allocation optimization
   - Workflow automation
   - Automated reporting
   - Performance analytics
   - AI-powered recommendations

## 🛠️ Technology Stack

- **Frontend:** Streamlit (Python-based web application framework)
- **UI Styling:** Custom CSS with Google Fonts (Gasoek One, Oswald)
- **Data Processing:** Pandas, Plotly
- **AI Integration:** OpenAI API support
- **Visualization:** Plotly Express, Plotly Graph Objects

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/robrita/azdemo.git
cd azdemo
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Set up environment variables:
Create a `.env` file in the root directory:
```
OPENAI_API_KEY=your_api_key_here
```

## 🚀 Usage

Run the Streamlit application:

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

## 📊 Dashboard Modules

### Dashboard Overview
- Key metrics visualization (Active Projects, Team Members, Completion Rate, On-Time Delivery)
- Project status distribution
- Monthly project trends
- Recent activities feed

### Skills Management
- Team skills distribution charts
- Add and track employee skills
- AI-powered skills gap analysis
- Training recommendations

### Document Analysis
- Upload documents (PDF, DOCX, TXT, CSV, XLSX)
- Multiple analysis types (Summary, Key Points, Risk Identification, Action Items, Compliance)
- Document repository management
- Analysis history tracking

### Project Monitoring
- Active projects overview with progress tracking
- Project timeline visualization
- Budget tracking and allocation charts
- Status indicators (On Track, At Risk, Delayed)

### PMO Operations
- Resource allocation matrix
- AI-powered resource optimization
- Workflow automation configuration
- Comprehensive report generation (PDF, Excel, PowerPoint, HTML)

## 🎨 UI/UX Features

- **Custom Styling:** Modern gradient-based design with custom CSS
- **Google Fonts:** Professional typography using Gasoek One and Oswald fonts
- **Responsive Layout:** Wide layout with expandable sidebar
- **Interactive Charts:** Dynamic Plotly visualizations
- **Color Scheme:** Professional blue gradient theme (#1E3A8A, #3B82F6)
- **Smooth Animations:** Hover effects and transitions

## 📁 Project Structure

```
azdemo/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md             # Project documentation
└── .gitignore           # Git ignore rules
```

## 🔐 Security

- Environment variables for sensitive data
- No hardcoded credentials
- Secure file upload handling
- Input validation

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is open source and available under the MIT License.

## 📧 Support

For support, please open an issue in the GitHub repository.

## 🎯 Roadmap

- [ ] Integration with real AI models (OpenAI, Azure AI)
- [ ] Database integration for persistent storage
- [ ] User authentication and authorization
- [ ] Advanced analytics and ML models
- [ ] Export/Import functionality
- [ ] Email notifications
- [ ] Mobile responsive design
- [ ] Multi-language support

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Charts powered by [Plotly](https://plotly.com/)
- Data processing with [Pandas](https://pandas.pydata.org/)
- Icons and fonts from [Google Fonts](https://fonts.google.com/)