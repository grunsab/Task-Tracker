# Task Tracker Commands & Guidelines

## Commands
- Run app: `python app.py`
- Install dependencies: `pip install -r requirements.txt` (create if needed)
- Initialize database: Automatic on first run

## Code Style Guidelines
- **Python**: Follow PEP 8 conventions
- **Indentation**: 4 spaces
- **Naming**:
  - Functions/variables: snake_case
  - Classes: PascalCase
  - Routes: lowercase with underscores
- **Imports**: Group by standard lib, third-party, local modules
- **Error Handling**: Use try/except blocks with specific exceptions
- **User Feedback**: Use Flask's flash() for user-facing messages
- **Templates**: Extend base.html for consistency
- **Documentation**: Add docstrings to new functions/methods
- **Database**: Use SQLAlchemy models with proper relationships

## Project Structure
- Flask application with SQLAlchemy and Jinja2 templates
- SQLite database stored in instance/ directory
- Templates in templates/ directory
- Static assets (CSS/JS) in static/ directory