import os
import sqlite3
import hashlib
from datetime import datetime

DB_PATH = os.path.join("data", "sunshine_orange.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _hash_password(password: str) -> str:
    # Simple salted hash for demo; replace with stronger hash in production.
    salt = "sunny_orange_"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            name TEXT,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_zh TEXT NOT NULL,
            name_en TEXT NOT NULL,
            category_zh TEXT,
            category_en TEXT,
            price REAL NOT NULL,
            desc_zh TEXT,
            desc_en TEXT,
            image_path TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            content TEXT NOT NULL,
            lang TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_zh TEXT NOT NULL,
            title_en TEXT NOT NULL,
            content_zh TEXT NOT NULL,
            content_en TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_zh TEXT NOT NULL,
            title_en TEXT NOT NULL,
            type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address_zh TEXT,
            address_en TEXT,
            phone TEXT,
            hours_zh TEXT,
            hours_en TEXT,
            map_embed TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name_zh TEXT,
            store_name_en TEXT,
            address_zh TEXT,
            address_en TEXT,
            phone TEXT,
            hours_zh TEXT,
            hours_en TEXT,
            map_embed TEXT,
            sort_order INTEGER DEFAULT 0,
            is_primary INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    # Lightweight migrations for existing databases.
    try:
        cur.execute("ALTER TABLE products ADD COLUMN category_zh TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE products ADD COLUMN category_en TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE contact_locations ADD COLUMN sort_order INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE contact_locations ADD COLUMN is_primary INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE contact_locations ADD COLUMN store_name_zh TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE contact_locations ADD COLUMN store_name_en TEXT")
    except sqlite3.OperationalError:
        pass

    # Migrate single contact_info to contact_locations if needed.
    try:
        cur.execute("SELECT COUNT(1) FROM contact_locations")
        has_locations = cur.fetchone()[0] > 0
        if not has_locations:
            cur.execute(
                "SELECT address_zh, address_en, phone, hours_zh, hours_en, map_embed FROM contact_info LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    """
                    INSERT INTO contact_locations
                    (address_zh, address_en, phone, hours_zh, hours_en, map_embed, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*row, datetime.utcnow().isoformat()),
                )
    except sqlite3.OperationalError:
        pass

    admin_username = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
    admin_password = os.getenv("ADMIN_PASSWORD", "88888888")
    now = datetime.utcnow().isoformat()

    # Ensure exactly one bootstrap admin credential is available from env.
    cur.execute("SELECT id FROM users WHERE role = ? ORDER BY id LIMIT 1", ("admin",))
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """
            INSERT INTO users (username, email, password_hash, name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                admin_username,
                "admin@sunshine.orange",
                _hash_password(admin_password),
                "Administrator",
                "admin",
                now,
            ),
        )
    else:
        cur.execute(
            "UPDATE users SET username = ?, password_hash = ? WHERE id = ?",
            (admin_username, _hash_password(admin_password), row[0]),
        )

    conn.commit()
    conn.close()


def verify_user(username: str, password: str) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, role, password_hash FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if _hash_password(password) != row[3]:
        return None
    return {"id": row[0], "username": row[1], "role": row[2]}


def create_user(username: str, password: str, name: str, email: str | None = None, role: str = "member") -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone() is not None:
        conn.close()
        return False
    cur.execute(
        """
        INSERT INTO users (username, email, password_hash, name, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            email,
            _hash_password(password),
            name,
            role,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return True


def update_user_profile(user_id: int, name: str, email: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (name, email, user_id))
    conn.commit()
    conn.close()


def list_users() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, name, email, role, created_at FROM users ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "username": r[1],
            "name": r[2],
            "email": r[3],
            "role": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


def delete_user(user_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_user_profile(user_id: int) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, name, email, role FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "username": row[1],
        "name": row[2],
        "email": row[3],
        "role": row[4],
    }


def add_product(
    name_zh: str,
    name_en: str,
    category_zh: str,
    category_en: str,
    price: float,
    desc_zh: str,
    desc_en: str,
    image_path: str | None,
    status: str = "active",
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO products (name_zh, name_en, category_zh, category_en, price, desc_zh, desc_en, image_path, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name_zh,
            name_en,
            category_zh,
            category_en,
            price,
            desc_zh,
            desc_en,
            image_path,
            status,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def list_products(active_only: bool = True, search: str | None = None, category: str | None = None) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    base_sql = """
        SELECT id, name_zh, name_en, category_zh, category_en, price, desc_zh, desc_en, image_path, status, created_at
        FROM products
    """
    clauses = []
    params: list = []
    if active_only:
        clauses.append("status = 'active'")
    if search:
        clauses.append("(name_zh LIKE ? OR name_en LIKE ? OR desc_zh LIKE ? OR desc_en LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if category:
        clauses.append("(category_zh = ? OR category_en = ?)")
        params.extend([category, category])
    if clauses:
        base_sql += " WHERE " + " AND ".join(clauses)
    base_sql += " ORDER BY created_at DESC"
    cur.execute(base_sql, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name_zh": r[1],
            "name_en": r[2],
            "category_zh": r[3],
            "category_en": r[4],
            "price": r[5],
            "desc_zh": r[6],
            "desc_en": r[7],
            "image_path": r[8],
            "status": r[9],
            "created_at": r[10],
        }
        for r in rows
    ]


def delete_product(product_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def add_message(user_name: str, content: str, lang: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (user_name, content, lang, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_name, content, lang, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def list_messages(limit: int | None = None) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    sql = "SELECT id, user_name, content, lang, created_at FROM messages ORDER BY created_at DESC"
    params = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "user_name": r[1],
            "content": r[2],
            "lang": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]


def delete_message(message_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()


def get_cart_items(user_id: int) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, product_id, qty FROM cart_items WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "product_id": r[1], "qty": r[2]} for r in rows]


def set_cart_item(user_id: int, product_id: int, qty: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM cart_items WHERE user_id = ? AND product_id = ?",
        (user_id, product_id),
    )
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE cart_items SET qty = ? WHERE id = ?", (qty, row[0]))
    else:
        cur.execute(
            """
            INSERT INTO cart_items (user_id, product_id, qty, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, product_id, qty, datetime.utcnow().isoformat()),
        )
    conn.commit()
    conn.close()


def remove_cart_item(user_id: int, product_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
        (user_id, product_id),
    )
    conn.commit()
    conn.close()


def clear_cart(user_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def create_order_from_cart(user_id: int) -> int | None:
    items = get_cart_items(user_id)
    if not items:
        return None
    products = {p["id"]: p for p in list_products(active_only=False)}
    total = 0.0
    for item in items:
        product = products.get(item["product_id"])
        if product:
            total += product["price"] * item["qty"]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO orders (user_id, total, status, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, total, "paid", datetime.utcnow().isoformat()),
    )
    order_id = cur.lastrowid
    for item in items:
        product = products.get(item["product_id"])
        if not product:
            continue
        cur.execute(
            """
            INSERT INTO order_items (order_id, product_id, qty, price)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, item["product_id"], item["qty"], product["price"]),
        )
    conn.commit()
    conn.close()
    clear_cart(user_id)
    return int(order_id)


def list_orders(user_id: int) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, total, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "total": r[1], "status": r[2], "created_at": r[3]}
        for r in rows
    ]


def list_order_items(order_id: int) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT oi.product_id, oi.qty, oi.price, p.name_zh, p.name_en
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
        """,
        (order_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "product_id": r[0],
            "qty": r[1],
            "price": r[2],
            "name_zh": r[3] or "",
            "name_en": r[4] or "",
        }
        for r in rows
    ]


def add_news(title_zh: str, title_en: str, content_zh: str, content_en: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO news (title_zh, title_en, content_zh, content_en, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title_zh, title_en, content_zh, content_en, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def list_news(limit: int | None = None) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    sql = "SELECT id, title_zh, title_en, content_zh, content_en, created_at FROM news ORDER BY created_at DESC"
    params = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "title_zh": r[1],
            "title_en": r[2],
            "content_zh": r[3],
            "content_en": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


def delete_news(news_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM news WHERE id = ?", (news_id,))
    conn.commit()
    conn.close()


def add_media(title_zh: str, title_en: str, media_type: str, file_path: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO media (title_zh, title_en, type, file_path, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title_zh, title_en, media_type, file_path, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def list_media() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title_zh, title_en, type, file_path, created_at FROM media ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "title_zh": r[1],
            "title_en": r[2],
            "type": r[3],
            "file_path": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


def delete_media(media_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM media WHERE id = ?", (media_id,))
    conn.commit()
    conn.close()


def get_contact_info() -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, address_zh, address_en, phone, hours_zh, hours_en, map_embed FROM contact_info LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "address_zh": row[1],
        "address_en": row[2],
        "phone": row[3],
        "hours_zh": row[4],
        "hours_en": row[5],
        "map_embed": row[6],
    }


def upsert_contact_info(
    address_zh: str,
    address_en: str,
    phone: str,
    hours_zh: str,
    hours_en: str,
    map_embed: str,
) -> None:
    existing = get_contact_info()
    conn = get_conn()
    cur = conn.cursor()
    if existing:
        cur.execute(
            """
            UPDATE contact_info
            SET address_zh = ?, address_en = ?, phone = ?, hours_zh = ?, hours_en = ?, map_embed = ?
            WHERE id = ?
            """,
            (
                address_zh,
                address_en,
                phone,
                hours_zh,
                hours_en,
                map_embed,
                existing["id"],
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO contact_info (address_zh, address_en, phone, hours_zh, hours_en, map_embed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (address_zh, address_en, phone, hours_zh, hours_en, map_embed),
        )
    conn.commit()
    conn.close()


def add_contact_location(
    store_name_zh: str,
    store_name_en: str,
    address_zh: str,
    address_en: str,
    phone: str,
    hours_zh: str,
    hours_en: str,
    map_embed: str,
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(sort_order), 0) FROM contact_locations")
    next_sort = (cur.fetchone()[0] or 0) + 1
    cur.execute(
        """
        INSERT INTO contact_locations
        (store_name_zh, store_name_en, address_zh, address_en, phone, hours_zh, hours_en, map_embed, sort_order, is_primary, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            store_name_zh,
            store_name_en,
            address_zh,
            address_en,
            phone,
            hours_zh,
            hours_en,
            map_embed,
            next_sort,
            0,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def list_contact_locations() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, store_name_zh, store_name_en, address_zh, address_en, phone, hours_zh, hours_en, map_embed, sort_order, is_primary, created_at
        FROM contact_locations
        ORDER BY is_primary DESC, sort_order ASC, created_at DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "store_name_zh": r[1],
            "store_name_en": r[2],
            "address_zh": r[3],
            "address_en": r[4],
            "phone": r[5],
            "hours_zh": r[6],
            "hours_en": r[7],
            "map_embed": r[8],
            "sort_order": r[9],
            "is_primary": r[10],
            "created_at": r[11],
        }
        for r in rows
    ]


def delete_contact_location(location_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM contact_locations WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()


def update_contact_location(
    location_id: int,
    store_name_zh: str,
    store_name_en: str,
    address_zh: str,
    address_en: str,
    phone: str,
    hours_zh: str,
    hours_en: str,
    map_embed: str,
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE contact_locations
        SET store_name_zh = ?, store_name_en = ?, address_zh = ?, address_en = ?, phone = ?, hours_zh = ?, hours_en = ?, map_embed = ?
        WHERE id = ?
        """,
        (
            store_name_zh,
            store_name_en,
            address_zh,
            address_en,
            phone,
            hours_zh,
            hours_en,
            map_embed,
            location_id,
        ),
    )
    conn.commit()
    conn.close()


def set_primary_location(location_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE contact_locations SET is_primary = 0")
    cur.execute("UPDATE contact_locations SET is_primary = 1 WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()


def update_location_sort(location_id: int, direction: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, sort_order FROM contact_locations WHERE id = ?",
        (location_id,),
    )
    current = cur.fetchone()
    if not current:
        conn.close()
        return
    current_order = current[1] or 0
    if direction == "up":
        cur.execute(
            "SELECT id, sort_order FROM contact_locations WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1",
            (current_order,),
        )
    else:
        cur.execute(
            "SELECT id, sort_order FROM contact_locations WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1",
            (current_order,),
        )
    neighbor = cur.fetchone()
    if neighbor:
        cur.execute(
            "UPDATE contact_locations SET sort_order = ? WHERE id = ?",
            (neighbor[1], current[0]),
        )
        cur.execute(
            "UPDATE contact_locations SET sort_order = ? WHERE id = ?",
            (current_order, neighbor[0]),
        )
    conn.commit()
    conn.close()


def set_setting(key: str, value: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO site_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_setting(key: str) -> str | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM site_settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


if __name__ == "__main__":
    init_db()
