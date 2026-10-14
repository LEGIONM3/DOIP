"""Hostile Audit: Level 2 & Level 3 - Backend Code & Database Reality Audit."""

import os
import sys
import ast
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Set

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./backend"))

from sqlalchemy import create_engine, inspect
from backend.app.models import Base
from backend.app.db import get_engine, get_database_url


def audit_database() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 3] Database Schema & Migration Reality Audit ---")
    results = {}
    
    # 1. Inspect configured database engine
    app_engine = get_engine()
    inspector = inspect(app_engine)
    existing_tables = inspector.get_table_names()
    print(f"Existing tables in active DB: {len(existing_tables)} tables")
    
    # 2. Inspect SQLAlchemy Declarative Base models
    model_tables = list(Base.metadata.tables.keys())
    print(f"Declared tables in ORM models (models.py): {len(model_tables)} tables")
    
    # 3. Check for orphan tables or missing tables
    missing_in_db = [t for t in model_tables if t not in existing_tables]
    untracked_in_models = [t for t in existing_tables if t not in model_tables]
    
    print(f"Tables in models but missing in DB: {missing_in_db}")
    print(f"Tables in DB but untracked in ORM models: {untracked_in_models}")
    
    # 4. Deep column inspection per table
    table_details = {}
    for table_name in model_tables:
        if table_name in existing_tables:
            columns = inspector.get_columns(table_name)
            pk = inspector.get_pk_constraint(table_name)
            fks = inspector.get_foreign_keys(table_name)
            indexes = inspector.get_indexes(table_name)
            table_details[table_name] = {
                "column_count": len(columns),
                "columns": [c["name"] for c in columns],
                "primary_key": pk.get("constrained_columns", []),
                "foreign_keys_count": len(fks),
                "indexes_count": len(indexes),
            }
            
    # 5. Check Alembic migrations
    alembic_dir = Path("backend/alembic/versions")
    migrations = []
    if alembic_dir.exists():
        migrations = [f.name for f in alembic_dir.glob("*.py")]
    print(f"Alembic migration versions found: {len(migrations)}")

    # 6. Test Fresh In-Memory SQLite Installation
    test_engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(test_engine)
        test_inspector = inspect(test_engine)
        fresh_tables = test_inspector.get_table_names()
        fresh_install_success = len(fresh_tables) == len(model_tables)
        print(f"Fresh installation test: {'SUCCESS' if fresh_install_success else 'FAILED'} ({len(fresh_tables)} created)")
    except Exception as ex:
        fresh_install_success = False
        print(f"Fresh installation test error: {ex}")
        fresh_tables = []

    return {
        "existing_tables_count": len(existing_tables),
        "model_tables_count": len(model_tables),
        "missing_in_db": missing_in_db,
        "untracked_in_models": untracked_in_models,
        "table_details": table_details,
        "migrations_count": len(migrations),
        "migrations": migrations,
        "fresh_install_success": fresh_install_success,
    }


def audit_backend_code() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 2] Backend Dead Code & Reachability Audit ---")
    backend_dir = Path("backend/app")
    py_files = list(backend_dir.glob("*.py"))
    
    # Map all defined files, functions, and imports
    file_imports: Dict[str, Set[str]] = {}
    file_definitions: Dict[str, List[str]] = {}
    
    for f in py_files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                tree = ast.parse(fp.read(), filename=str(f))
            imports = set()
            defs = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.add(name.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
                elif isinstance(node, ast.FunctionDef):
                    defs.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    defs.append(node.name)
            file_imports[f.stem] = imports
            file_definitions[f.stem] = defs
        except Exception as ex:
            print(f"Failed to parse {f.name}: {ex}")

    # Check which modules are imported by other modules or tests
    all_code_files = list(Path("backend").glob("**/*.py")) + list(Path("tests").glob("*.py"))
    all_imports_text = ""
    for cf in all_code_files:
        try:
            with open(cf, "r", encoding="utf-8") as fp:
                all_imports_text += "\n" + fp.read()
        except Exception:
            pass

    unreferenced_modules = []
    for mod_name in file_imports.keys():
        if mod_name in ["main", "__init__"]:
            continue
        # Search if mod_name is imported or referenced
        patterns = [f"import {mod_name}", f"from .{mod_name}", f"from backend.app.{mod_name}", f"from app.{mod_name}", f"from .{mod_name} import", f".{mod_name}"]
        referenced = any(p in all_imports_text for p in patterns)
        if not referenced:
            unreferenced_modules.append(mod_name)

    print(f"Total backend top-level modules: {len(py_files)}")
    print(f"Unreferenced / potentially dead modules: {unreferenced_modules}")

    return {
        "total_modules": len(py_files),
        "unreferenced_modules": unreferenced_modules,
        "module_definitions_count": {k: len(v) for k, v in file_definitions.items()},
    }


if __name__ == "__main__":
    db_res = audit_database()
    backend_res = audit_backend_code()

    out_file = Path("docs/verification/database_backend_audit.json")
    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump({"database": db_res, "backend": backend_res}, fp, indent=2)
    print(f"\nAudit results persisted to {out_file}")
