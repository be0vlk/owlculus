"""
This package contains various utility functions and classes used throughout the app.

app_setup.py: Automatically runs whenever the main app is launched via the command line if no migrations folder is
found. Automates a lot of the initialization and setup. Can be run directly with '--migrate' for quick migration
after schema changes.

db.py: Just initialize sqlalchemy here so that it can be easily imported elsewhere, avoiding circular imports.

helpers.py: Assorted reusable functions called in various places by the API backend.

models.py: The database models for the app's database used by SQLAlchemy and throughout the code.
"""