from models.neo4j_client import db


class AuthService:
    def register(self, role: str, name: str, email: str, password: str) -> dict | None:
        if role == "student":
            return db.register_student(name, email, password)
        if role == "teacher":
            return db.register_teacher(name, email, password)
        if role == "admin":
            return db.create_admin(name, email, password)
        return None

    def login(self, role: str, email: str, password: str) -> dict | None:
        if role == "student":
            return db.login_student(email, password)
        if role == "teacher":
            return db.login_teacher(email, password)
        if role == "admin":
            return db.login_admin(email, password)
        return None

    def resolve_token(self, token: str) -> dict | None:
        return db.get_user_by_token(token)

    def refresh_token(self, token: str) -> dict | None:
        return db.refresh_user_token(token)

    def revoke_token(self, token: str) -> bool:
        return db.revoke_user_token(token)


auth_service = AuthService()
