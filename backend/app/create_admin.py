"""Create an ADMIN account:  python -m app.create_admin [--name N] [--email E]
The password is always prompted (or read from VF_ADMIN_PASSWORD for non-interactive setup)."""
import argparse
import asyncio
import getpass
import os
import sys

from . import db as dbmod
from .config import get_settings
from .security import password_problems
from .services.users import EmailTaken, create_user
from .services import audit


async def main() -> int:
    ap = argparse.ArgumentParser(description="Create a VisualFind administrator")
    ap.add_argument("--name")
    ap.add_argument("--email")
    args = ap.parse_args()
    name = args.name or input("Name: ").strip()
    email = (args.email or input("Email: ")).strip().lower()
    password = os.environ.get("VF_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Password: ")
        if getpass.getpass("Confirm password: ") != password:
            print("Passwords do not match.", file=sys.stderr)
            return 1
    problems = password_problems(password)
    if len(name) < 2 or "@" not in email or problems:
        print("Invalid input. " + ("Password must contain " + ", ".join(problems) if problems else ""), file=sys.stderr)
        return 1
    s = get_settings()
    client, db = dbmod.connect(s.mongodb_uri, s.mongodb_db_name)
    await dbmod.ensure_indexes(db)
    try:
        user = await create_user(db, name, email, password, role="ADMIN")
    except EmailTaken:
        print(f"An account with {email} already exists.", file=sys.stderr)
        return 1
    await audit.record(db, "admin.created", actor=user, target=user["_id"], metadata={"via": "cli"})
    print(f"Admin created: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
