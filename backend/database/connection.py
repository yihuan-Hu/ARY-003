import os
import sqlite3

from flask import current_app, has_app_context


def database_path():
    if has_app_context():
        return current_app.config['DATABASE']
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.environ.get('ORGANIZER_DB', os.path.join(base_dir, 'organizer.db'))


def get_db():
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn
