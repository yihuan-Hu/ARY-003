from database import get_db
from daos import UserDAO
from utils.auth import issue_token, verify_password
from utils.errors import AppError, ValidationError


class AuthService:
    @staticmethod
    def login(data):
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            raise ValidationError('username and password are required')

        conn = get_db()
        try:
            user = UserDAO.get_by_username(conn, username)
            if not user or not verify_password(password, user['password_hash']):
                raise AppError('Invalid username or password', 401)
            return {
                'token': issue_token(user),
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                },
            }
        finally:
            conn.close()
