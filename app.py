import os
import random
import sqlite3
from datetime import datetime
import io
import csv
import base64
import re
from urllib.parse import quote, urlparse, parse_qs, unquote
import re

import streamlit as st

from db import (
    init_db,
    get_conn,
    verify_user,
    create_user,
    get_user_profile,
    update_user_profile,
    list_users,
    delete_user,
    add_news,
    list_news,
    delete_news,
    add_media,
    list_media as list_media_db,
    delete_media,
    get_contact_info,
    upsert_contact_info,
    add_contact_location,
    list_contact_locations,
    delete_contact_location,
    set_primary_location,
    update_location_sort,
    update_contact_location,
    set_setting,
    get_setting,
    add_product,
    list_products,
    delete_product,
    add_message,
    list_messages,
    delete_message,
    get_cart_items,
    set_cart_item,
    remove_cart_item,
    clear_cart,
    create_order_from_cart,
    list_orders,
    list_order_items,
)
from i18n import t


APP_TITLE = "Sunshine Orange"
ASSETS_GIFS = os.path.join("assets", "gifs")
ASSETS_IMAGES = os.path.join("assets", "images")
ASSETS_VIDEOS = os.path.join("assets", "videos")


def list_local_media(folder: str, exts: tuple[str, ...]) -> list[str]:
    if not os.path.isdir(folder):
        return []
    files = [os.path.join(folder, f) for f in os.listdir(folder)]
    return [f for f in files if os.path.splitext(f)[1].lower() in exts]


def _build_maps_embed_url(value: str) -> str:
    value = value.strip()
    if value.startswith("http"):
        try:
            parsed = urlparse(value)
            qs = parse_qs(parsed.query)
            if "q" in qs and qs["q"]:
                q = qs["q"][0]
                return f"https://www.google.com/maps?q={quote(q)}&output=embed"
            match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", value)
            if match:
                lat, lng = match.group(1), match.group(2)
                return f"https://www.google.com/maps?q={lat},{lng}&output=embed"
            if "/place/" in value:
                place = value.split("/place/")[1].split("/")[0]
                place = unquote(place.replace("+", " "))
                return f"https://www.google.com/maps?q={quote(place)}&output=embed"
        except Exception:
            pass
    return f"https://www.google.com/maps?q={quote(value)}&output=embed"


def _build_maps_nav_url(value: str) -> str:
    value = value.strip()
    dest = value
    if value.startswith("http"):
        try:
            parsed = urlparse(value)
            qs = parse_qs(parsed.query)
            if "q" in qs and qs["q"]:
                dest = qs["q"][0]
            else:
                match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", value)
                if match:
                    dest = f"{match.group(1)},{match.group(2)}"
                elif "/place/" in value:
                    place = value.split("/place/")[1].split("/")[0]
                    dest = unquote(place.replace("+", " "))
        except Exception:
            dest = value
    return f"https://www.google.com/maps/dir/?api=1&destination={quote(dest)}"


def load_latest_news(limit: int = 3) -> list[dict]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT title_zh, title_en, content_zh, content_en, created_at
            FROM news
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error:
        return []

    news = []
    for row in rows:
        news.append(
            {
                "title_zh": row[0],
                "title_en": row[1],
                "content_zh": row[2],
                "content_en": row[3],
                "created_at": row[4],
            }
        )
    return news


def set_page(page: str) -> None:
    st.session_state["page"] = page


def get_cart() -> dict:
    if "cart" not in st.session_state:
        st.session_state["cart"] = {}
    return st.session_state["cart"]


def is_member_logged_in() -> bool:
    return st.session_state.get("member_user") is not None


def add_to_cart(product_id: int) -> None:
    member = st.session_state.get("member_user")
    if member:
        items = get_cart_items(member["id"])
        existing = next((i for i in items if i["product_id"] == product_id), None)
        qty = existing["qty"] + 1 if existing else 1
        set_cart_item(member["id"], product_id, qty)
        return

    cart = get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    st.session_state["cart"] = cart


def render_topbar(lang: str) -> None:
    col_left, col_right = st.columns([5, 0.8])
    with col_left:
        st.markdown(
            f"<div class='brand' role='button'>{t('site_name', lang)}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='tagline'>{t('tagline', lang)}</div>",
            unsafe_allow_html=True,
        )
        nav_icons = {
            "home": "🍊",
            "products": "🍹",
            "find_us": "📍",
            "messages": "💬",
            "member": "🍓",
            "cart": "🛒",
            "media": "🍇",
        }
        base_labels = [
            t("nav_home", lang),
            t("nav_products", lang),
            t("nav_find_us", lang),
            t("nav_messages", lang),
            t("nav_member", lang),
            t("nav_media", lang),
        ]
        nav_items = [
            (f"{nav_icons['home']} {base_labels[0]}", "home"),
            (f"{nav_icons['products']} {base_labels[1]}", "products"),
            (f"{nav_icons['find_us']} {base_labels[2]}", "find_us"),
            (f"{nav_icons['messages']} {base_labels[3]}", "messages"),
            (f"{nav_icons['member']} {base_labels[4]}", "member"),
            (f"{nav_icons['media']} {base_labels[5]}", "media"),
        ]
        weights = []
        for label in base_labels:
            l = len(label)
            if l <= 2:
                w = 1.0
            elif l <= 4:
                w = 1.15
            elif l <= 6:
                w = 1.35
            else:
                w = 1.6
            if label == "到哪裡找我們":
                w += 0.6
            elif label == "會員中心":
                w += 0.3
            weights.append(w)
        nav_cols = st.columns(weights, gap="small")
        for col, (label, page) in zip(nav_cols, nav_items):
            with col:
                if st.button(label, key=f"top_{page}", use_container_width=True):
                    set_page(page)
                    st.rerun()
    with col_right:
        if st.button(t("login", lang), use_container_width=True, key="login_btn"):
            set_page("admin")
            st.rerun()


def render_home(lang: str) -> None:
    st_autorefresh = getattr(st, "autorefresh", None)
    if st_autorefresh:
        st_autorefresh(interval=5000, key="fruit_anim_refresh")

    render_topbar(lang)

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown(
            "<div class='section-title'>" + t("media_spotlight", lang) + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='section-sub'>" + t("home_intro", lang) + "</div>",
            unsafe_allow_html=True,
        )

        hero_video = os.path.join(ASSETS_VIDEOS, "jimeng.mp4")
        hero_setting = get_setting("home_hero_media")
        if hero_setting and os.path.exists(hero_setting):
            hero_video = hero_setting
        if os.path.exists(hero_video):
            with open(hero_video, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            video_html = f"""
<video
  src="data:video/mp4;base64,{data}"
  autoplay
  muted
  loop
  playsinline
  controls
  controlslist="nodownload noplaybackrate"
  style="width:100%; border-radius:16px; box-shadow: 0 10px 24px rgba(255, 179, 162, 0.25);">
</video>
"""
            st.components.v1.html(video_html, height=420)
        else:
            gifs = list_local_media(ASSETS_GIFS, (".gif", ".png", ".jpg", ".jpeg"))
            if gifs:
                selected = random.choice(gifs)
                st.image(selected, use_column_width=True)
            else:
                st.markdown(
                    "<div class='placeholder'>" + t("add_gifs", lang) + "</div>",
                    unsafe_allow_html=True,
                )

    with right:
        st.markdown(
            "<div class='section-title'>" + t("latest_news", lang) + "</div>",
            unsafe_allow_html=True,
        )
        news = load_latest_news()
        if not news:
            st.markdown(
                "<div class='card'>" + t("no_news", lang) + "</div>",
                unsafe_allow_html=True,
            )
        else:
            for item in news:
                title = item["title_zh"] if lang == "zh" else item["title_en"]
                content = item["content_zh"] if lang == "zh" else item["content_en"]
                st.markdown(
                    f"<div class='card'><div class='card-title'>{title}</div><div class='card-body'>{content}</div></div>",
                    unsafe_allow_html=True,
                )

    # 功能選單已取消


def render_products(lang: str) -> None:
    render_topbar(lang)
    st.markdown(
        f"<div class='section-title'>{t('products_title', lang)}</div>",
        unsafe_allow_html=True,
    )

    all_products = list_products(active_only=True)
    categories = []
    for p in all_products:
        cat = p["category_zh"] if lang == "zh" else p["category_en"]
        if cat and cat not in categories:
            categories.append(cat)

    search = st.text_input(t("product_search", lang))
    category = st.selectbox(t("product_category", lang), ["All / 全部"] + categories)
    selected_category = None if category == "All / 全部" else category

    products = list_products(active_only=True, search=search or None, category=selected_category)
    if not products:
        st.markdown(f"<div class='card'>{t('no_products', lang)}</div>", unsafe_allow_html=True)
        return

    cols_per_row = 3
    rows = [products[i : i + cols_per_row] for i in range(0, len(products), cols_per_row)]
    for row in rows:
        cols = st.columns(cols_per_row, gap="large")
        for col, product in zip(cols, row):
            with col:
                name = product["name_zh"] if lang == "zh" else product["name_en"]
                desc = product["desc_zh"] if lang == "zh" else product["desc_en"]
                cat = product["category_zh"] if lang == "zh" else product["category_en"]
                st.markdown("<div class='product-card'>", unsafe_allow_html=True)
                if product["image_path"] and os.path.exists(product["image_path"]):
                    st.image(product["image_path"], use_column_width=True)
                else:
                    st.markdown("<div class='placeholder'>無圖片 / No Image</div>", unsafe_allow_html=True)
                if cat:
                    st.markdown(f"<div class='badge'>{cat}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='card-title'>{name}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='card-body'>{desc}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='price'>{t('price', lang)}: {product['price']:.2f}</div>", unsafe_allow_html=True)
                if st.button(t("add_to_cart", lang), key=f"add_cart_{product['id']}"):
                    add_to_cart(product["id"])
                    st.success(t("add_to_cart", lang))
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)


def render_cart(lang: str) -> None:
    render_topbar(lang)
    st.markdown(
        f"<div class='section-title'>{t('cart_title', lang)}</div>",
        unsafe_allow_html=True,
    )

    member = st.session_state.get("member_user")
    cart = get_cart()

    if member:
        db_items = get_cart_items(member["id"])
        cart = {str(i["product_id"]): i["qty"] for i in db_items}

    if not cart:
        st.markdown(f"<div class='card'>{t('cart_empty', lang)}</div>", unsafe_allow_html=True)
        return

    products = {p["id"]: p for p in list_products(active_only=False)}
    total = 0.0

    for pid, qty in list(cart.items()):
        product = products.get(int(pid))
        if not product:
            continue
        name = product["name_zh"] if lang == "zh" else product["name_en"]
        price = product["price"]
        total += price * qty

        with st.container():
            st.markdown(f"<div class='card-title'>{name}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card-body'>{t('price', lang)}: {price:.2f}</div>", unsafe_allow_html=True)
            new_qty = st.number_input(
                f"{t('quantity', lang)}",
                min_value=0,
                value=int(qty),
                step=1,
                key=f"qty_{pid}",
            )
            if new_qty == 0:
                if st.button(t("remove", lang), key=f"remove_{pid}"):
                    if member:
                        remove_cart_item(member["id"], int(pid))
                    else:
                        cart.pop(pid, None)
                        st.session_state["cart"] = cart
                    st.rerun()
            else:
                if member:
                    set_cart_item(member["id"], int(pid), int(new_qty))
                else:
                    cart[pid] = int(new_qty)

    st.markdown(f"<div class='card'>{t('cart_total', lang)}: {total:.2f}</div>", unsafe_allow_html=True)

    if member:
        if st.button(t("checkout", lang)):
            order_id = create_order_from_cart(member["id"])
            if order_id:
                st.success(f"訂單已建立 / Order #{order_id} created")
                st.rerun()
    else:
        st.info("請先登入會員以結帳 / Please sign in to checkout")

    if st.button(t("cart_clear", lang)):
        if member:
            clear_cart(member["id"])
        else:
            st.session_state["cart"] = {}
        st.rerun()

    if member:
        # Build LINE message with order details
        lines = [f"您好，我要下單。", f"會員：{member['username']}"]
        for pid, qty in list(cart.items()):
            product = products.get(int(pid))
            if not product:
                continue
            name = product["name_zh"] if lang == "zh" else product["name_en"]
            lines.append(f"- {name} x {qty}")
        lines.append(f"總金額：{total:.2f}")
        line_text = "\n".join(lines)
        line_url = f"https://line.me/R/msg/text/?{quote(line_text)}"
        st.markdown(
            f"<a class='nav-pill' href='{line_url}' target='_blank'>LINE 結帳 / Line Checkout</a>",
            unsafe_allow_html=True,
        )


def _build_orders_csv(orders: list[dict], lang: str) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["order_id", "status", "total", "created_at", "item_name", "qty", "price"]
    writer.writerow(header)
    for order in orders:
        items = list_order_items(order["id"])
        if not items:
            writer.writerow([order["id"], order["status"], order["total"], order["created_at"], "", "", ""])
            continue
        for item in items:
            name = item["name_zh"] if lang == "zh" else item["name_en"]
            writer.writerow(
                [
                    order["id"],
                    order["status"],
                    order["total"],
                    order["created_at"],
                    name,
                    item["qty"],
                    item["price"],
                ]
            )
    return output.getvalue().encode("utf-8")


def render_member(lang: str) -> None:
    render_topbar(lang)
    member = st.session_state.get("member_user")

    if member:
        st.markdown(
            f"<div class='section-title'>{t('member_welcome', lang)} {member['username']}</div>",
            unsafe_allow_html=True,
        )
        tabs = st.tabs([t("member_profile", lang), t("member_orders", lang)])

        with tabs[0]:
            profile = get_user_profile(member["id"]) or {}
            with st.form("profile_form"):
                name = st.text_input(t("member_name", lang), value=profile.get("name") or "")
                email = st.text_input(t("member_email", lang), value=profile.get("email") or "")
                submitted = st.form_submit_button(t("admin_save", lang))
            if submitted:
                update_user_profile(member["id"], name, email)
                st.success(t("admin_save", lang))
                st.rerun()

        with tabs[1]:
            orders = list_orders(member["id"])
            if not orders:
                st.markdown(f"<div class='card'>{t('orders_empty', lang)}</div>", unsafe_allow_html=True)
            else:
                csv_data = _build_orders_csv(orders, lang)
                st.download_button(
                    t("download_orders", lang),
                    data=csv_data,
                    file_name="orders.csv",
                    mime="text/csv",
                )
                for order in orders:
                    with st.expander(
                        f"訂單 / Order #{order['id']} - {order['status']} - {order['total']:.2f}",
                        expanded=False,
                    ):
                        items = list_order_items(order["id"])
                        if not items:
                            st.markdown(f"<div class='card'>{t('order_items', lang)}: 0</div>", unsafe_allow_html=True)
                        else:
                            for item in items:
                                name = item["name_zh"] if lang == "zh" else item["name_en"]
                                line = f"{name} x {item['qty']} = {item['price'] * item['qty']:.2f}"
                                st.markdown(f"<div class='card'>{line}</div>", unsafe_allow_html=True)

        if st.button(t("member_logout", lang)):
            st.session_state["member_user"] = None
            st.rerun()
        return

    tabs = st.tabs([t("member_login", lang), t("member_register", lang)])

    with tabs[0]:
        with st.form("member_login_form"):
            username = st.text_input(t("member_username", lang))
            password = st.text_input(t("member_password", lang), type="password")
            submitted = st.form_submit_button(t("member_login", lang))
        if submitted:
            user = verify_user(username, password)
            if user:
                st.session_state["member_user"] = user
                st.success(t("member_login", lang))
                st.rerun()
            else:
                st.error("帳號或密碼錯誤 / Invalid credentials")

    with tabs[1]:
        with st.form("member_register_form"):
            name = st.text_input(t("member_name", lang))
            username = st.text_input(t("member_username", lang), key="reg_username")
            email = st.text_input(t("member_email", lang), key="reg_email")
            password = st.text_input(t("member_password", lang), type="password", key="reg_password")
            st.markdown(
                "<div class='pw-hint'>密碼需含英數且至少8碼 / Password must be alphanumeric and at least 8 characters</div>",
                unsafe_allow_html=True,
            )
            submitted = st.form_submit_button(t("member_register", lang))
        if submitted:
            if not username or not password:
                st.error("請填寫帳號與密碼 / Please enter username and password")
            elif len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
                st.markdown(
                    "<div class='pw-hint'>密碼需含英數且至少8碼 / Password must be alphanumeric and at least 8 characters</div>",
                    unsafe_allow_html=True,
                )
            elif create_user(username, password, name, email, role="member"):
                user = verify_user(username, password)
                if user:
                    st.session_state["member_user"] = user
                st.success("註冊成功，已自動登入 / Registration successful, signed in")
                st.session_state["page"] = "member"
                st.rerun()
            else:
                st.error("帳號已存在 / Username already exists")


def render_messages(lang: str) -> None:
    render_topbar(lang)
    st.markdown(
        f"<div class='section-title'>{t('message_title', lang)}</div>",
        unsafe_allow_html=True,
    )

    messages = list_messages()
    if not messages:
        st.markdown(f"<div class='card'>{t('no_messages', lang)}</div>", unsafe_allow_html=True)
    else:
        for msg in messages:
            st.markdown(
                f"<div class='card'><div class='card-title'>{msg['user_name']}</div><div class='card-body'>{msg['content']}</div></div>",
                unsafe_allow_html=True,
            )

    with st.form("message_form", clear_on_submit=True):
        member = st.session_state.get("member_user")
        name_default = member["username"] if member else ""
        name = st.text_input(t("message_name", lang), value=name_default, disabled=member is not None)
        content = st.text_area(t("message_content", lang))
        submitted = st.form_submit_button(t("message_post", lang))
    if submitted:
        if not name or not content:
            st.error("請輸入暱稱與留言內容 / Please enter name and message")
        else:
            try:
                add_message(name, content, lang)
                st.success(t("message_post", lang))
                st.rerun()
            except Exception:
                st.error("留言送出失敗 / Failed to post message")


def render_find_us(lang: str) -> None:
    render_topbar(lang)
    st.markdown(
        f"<div class='section-title'>{t('nav_find_us', lang)}</div>",
        unsafe_allow_html=True,
    )
    locations = list_contact_locations()
    if not locations:
        info = get_contact_info()
        if not info:
            st.markdown(f"<div class='card'>{t('coming_soon', lang)}</div>", unsafe_allow_html=True)
            return
        locations = [info]

    for info in locations:
        store_name = info.get("store_name_zh") if lang == "zh" else info.get("store_name_en")
        address = info["address_zh"] if lang == "zh" else info["address_en"]
        hours = info["hours_zh"] if lang == "zh" else info["hours_en"]
        if info.get("is_primary"):
            st.markdown("<div class='badge'>主店 / Primary</div>", unsafe_allow_html=True)
        if store_name:
            st.markdown(
                f"<div class='card'><div class='card-title'>店名 / Store</div>{store_name}</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div class='card'><div class='card-title'>地址 / Address</div>{address}</div>",
            unsafe_allow_html=True,
        )
        hours_display = (hours or "").replace("\n", "<br>")
        st.markdown(
            f"<div class='card'><div class='card-title'>營業時間 / Hours</div>{hours_display}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='card'><div class='card-title'>電話 / Phone</div>{info.get('phone','')}</div>",
            unsafe_allow_html=True,
        )
        if info.get("map_embed"):
            map_value = info["map_embed"].strip()
            if map_value.startswith("<iframe"):
                st.markdown(map_value, unsafe_allow_html=True)
            else:
                embed_url = _build_maps_embed_url(map_value)
                nav_url = _build_maps_nav_url(map_value)
                st.components.v1.html(
                    f"""
<div style="position:relative; width:100%; height:360px;">
  <iframe
    src="{embed_url}"
    width="100%"
    height="360"
    style="border:0; border-radius:16px; box-shadow: 0 10px 24px rgba(255, 179, 162, 0.25);"
    allowfullscreen=""
    loading="lazy"
    referrerpolicy="no-referrer-when-downgrade">
  </iframe>
  <a href="{nav_url}" target="_blank" rel="noopener"
     style="position:absolute; inset:0; border-radius:16px; display:block;"></a>
</div>
""",
                    height=380,
                )


def render_media(lang: str) -> None:
    render_topbar(lang)
    st.markdown(
        f"<div class='section-title'>{t('media_title', lang)}</div>",
        unsafe_allow_html=True,
    )
    items = list_media_db()
    if not items:
        st.markdown(f"<div class='card'>{t('no_media', lang)}</div>", unsafe_allow_html=True)
        return

    for item in items:
        title = item["title_zh"] if lang == "zh" else item["title_en"]
        st.markdown(f"<div class='card-title'>{title}</div>", unsafe_allow_html=True)
        if item["type"] in ("gif", "image"):
            st.image(item["file_path"], use_column_width=True)
        else:
            st.video(item["file_path"])


def save_uploaded_file(uploaded, folder: str) -> str:
    os.makedirs(folder, exist_ok=True)
    name = os.path.basename(uploaded.name)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{timestamp}_{name}"
    path = os.path.join(folder, safe_name)
    with open(path, "wb") as f:
        f.write(uploaded.getbuffer())
    return path


def render_admin(lang: str) -> None:
    render_topbar(lang)

    if not st.session_state.get("admin_authenticated"):
        st.markdown(
            f"<div class='section-title'>{t('admin_login_title', lang)}</div>",
            unsafe_allow_html=True,
        )
        with st.form("admin_login_form"):
            username = st.text_input(t("admin_username", lang))
            password = st.text_input(t("admin_password", lang), type="password")
            submitted = st.form_submit_button(t("admin_signin", lang))
        if submitted:
            user = verify_user(username, password)
            if user and user["role"] == "admin":
                st.session_state["admin_authenticated"] = True
                st.success(t("admin_logged_in", lang))
                st.rerun()
            else:
                st.error("帳號或密碼錯誤 / Invalid credentials")
        return

    top_left, top_right = st.columns([3, 1])
    with top_left:
        st.markdown(
            f"<div class='section-title'>{t('nav_admin', lang)}</div>",
            unsafe_allow_html=True,
        )
    with top_right:
        if st.button(t("admin_logout", lang), use_container_width=True):
            st.session_state["admin_authenticated"] = False
            st.rerun()

    tabs = st.tabs(
        [
            t("admin_products", lang),
            t("admin_news", lang),
            t("admin_media", lang),
            t("admin_contact", lang),
            t("admin_messages", lang),
            "會員管理 / Members",
        ]
    )

    with tabs[0]:
        st.markdown("<div class='section-sub'>" + t("admin_products", lang) + "</div>", unsafe_allow_html=True)
        with st.form("product_form"):
            name_zh = st.text_input("Name (中文)")
            name_en = st.text_input("Name (English)")
            category_zh = st.text_input("分類 (中文)")
            category_en = st.text_input("Category (English)")
            price = st.number_input(t("price", lang), min_value=0.0, step=1.0)
            desc_zh = st.text_area("Description (中文)")
            desc_en = st.text_area("Description (English)")
            status = st.selectbox("狀態 / Status", ["active", "inactive"])
            uploaded = st.file_uploader("產品圖片 / Product Image", type=["png", "jpg", "jpeg", "gif"])
            submitted = st.form_submit_button(t("admin_add", lang))
        if submitted:
            image_path = None
            if uploaded is not None:
                image_path = save_uploaded_file(uploaded, ASSETS_IMAGES)
            add_product(name_zh, name_en, category_zh, category_en, price, desc_zh, desc_en, image_path, status)
            st.success(t("admin_add", lang))
            st.rerun()

        for product in list_products(active_only=False):
            name = product["name_zh"] if lang == "zh" else product["name_en"]
            st.markdown(f"<div class='card-title'>{name}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card-body'>狀態 / Status: {product['status']}</div>", unsafe_allow_html=True)
            if product["image_path"] and os.path.exists(product["image_path"]):
                st.image(product["image_path"], use_column_width=True)
            if st.button(t("admin_delete", lang), key=f"del_product_{product['id']}"):
                delete_product(product["id"])
                st.rerun()

    with tabs[1]:
        st.markdown("<div class='section-sub'>" + t("admin_news", lang) + "</div>", unsafe_allow_html=True)
        with st.form("news_form"):
            title_zh = st.text_input("Title (中文)")
            title_en = st.text_input("Title (English)")
            content_zh = st.text_area("Content (中文)")
            content_en = st.text_area("Content (English)")
            submitted = st.form_submit_button(t("admin_add", lang))
        if submitted and title_zh:
            safe_title_en = title_en or title_zh
            safe_content_en = content_en or content_zh
            add_news(title_zh, safe_title_en, content_zh, safe_content_en)
            st.success(t("admin_add", lang))
            st.rerun()

        for item in list_news():
            display_title = item["title_zh"] if lang == "zh" else item["title_en"]
            display_content = item["content_zh"] if lang == "zh" else item["content_en"]
            st.markdown(
                f"<div class='card'><div class='card-title'>{display_title}</div><div class='card-body'>{display_content}</div></div>",
                unsafe_allow_html=True,
            )
            if st.button(t("admin_delete", lang), key=f"del_news_{item['id']}"):
                delete_news(item["id"])
                st.rerun()

    with tabs[2]:
        st.markdown("<div class='section-sub'>" + t("admin_media", lang) + "</div>", unsafe_allow_html=True)
        with st.form("media_form"):
            title_zh = st.text_input("Title (中文)", key="media_title_zh")
            title_en = st.text_input("Title (English)", key="media_title_en")
            uploaded = st.file_uploader(
                t("admin_upload", lang),
                type=["gif", "png", "jpg", "jpeg", "mp4", "webm"],
            )
            submitted = st.form_submit_button(t("admin_add", lang))
        if submitted and uploaded is not None:
            ext = os.path.splitext(uploaded.name)[1].lower()
            if ext in (".gif",):
                media_type = "gif"
                folder = ASSETS_GIFS
            elif ext in (".png", ".jpg", ".jpeg"):
                media_type = "image"
                folder = ASSETS_IMAGES
            else:
                media_type = "video"
                folder = ASSETS_VIDEOS
            file_path = save_uploaded_file(uploaded, folder)
            add_media(title_zh or uploaded.name, title_en or uploaded.name, media_type, file_path)
            st.success(t("admin_add", lang))
            st.rerun()

        for item in list_media_db():
            title = item["title_zh"] if lang == "zh" else item["title_en"]
            st.markdown(f"<div class='card-title'>{title}</div>", unsafe_allow_html=True)
            if item["type"] in ("gif", "image"):
                st.image(item["file_path"], use_column_width=True)
            else:
                st.video(item["file_path"])
            if st.button(t("admin_delete", lang), key=f"del_media_{item['id']}"):
                delete_media(item["id"])
                st.rerun()

        st.markdown("<div class='section-sub'>首頁影音主題設定</div>", unsafe_allow_html=True)
        media_items = list_media_db()
        options = ["jimeng.mp4 (預設)"] + [f"{m['id']} - {m['title_zh']}" for m in media_items]
        current = get_setting("home_hero_media")
        selected = st.selectbox("選擇首頁動畫", options, index=0)
        if st.button("套用首頁動畫"):
            if selected == "jimeng.mp4 (預設)":
                set_setting("home_hero_media", os.path.join(ASSETS_VIDEOS, "jimeng.mp4"))
            else:
                media_id = int(selected.split(" - ")[0])
                chosen = next((m for m in media_items if m["id"] == media_id), None)
                if chosen:
                    set_setting("home_hero_media", chosen["file_path"])
            st.success("已更新首頁動畫")
            st.rerun()

    with tabs[3]:
        st.markdown("<div class='section-sub'>" + t("admin_contact", lang) + "</div>", unsafe_allow_html=True)
        with st.form("contact_form"):
            store_name_zh = st.text_input("店名 (中文)")
            store_name_en = st.text_input("Store Name (English)")
            address_zh = st.text_area("地址 (中文)", height=80)
            address_en = st.text_area("地址 (English) / Address", height=80)
            phone = st.text_input("電話 / Phone")
            hours_zh = st.text_area("營業時間 (中文)", height=100)
            hours_en = st.text_area("Hours (English) / 營業時間", height=100)
            map_embed = st.text_area("地圖嵌入 / Map Embed")
            submitted = st.form_submit_button(t("admin_add", lang))
        if submitted:
            add_contact_location(
                store_name_zh,
                store_name_en,
                address_zh,
                address_en,
                phone,
                hours_zh,
                hours_en,
                map_embed,
            )
            st.success(t("admin_add", lang))
            st.rerun()

        for loc in list_contact_locations():
            title = loc.get("store_name_zh") or loc.get("store_name_en") or loc["address_zh"] or loc["address_en"] or "Location"
            badge = "（主店）" if loc.get("is_primary") else ""
            st.markdown(f"<div class='card-title'>{title} {badge}</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='card-body'>{loc.get('phone','')}</div>",
                unsafe_allow_html=True,
            )
            with st.expander("編輯資訊"):
                with st.form(f"edit_loc_{loc['id']}"):
                    edit_store_zh = st.text_input("店名 (中文)", value=loc.get("store_name_zh", ""))
                    edit_store_en = st.text_input("Store Name (English)", value=loc.get("store_name_en", ""))
                    edit_address_zh = st.text_area("地址 (中文)", value=loc.get("address_zh", ""), height=80)
                    edit_address_en = st.text_area("地址 (English) / Address", value=loc.get("address_en", ""), height=80)
                    edit_phone = st.text_input("電話 / Phone", value=loc.get("phone", ""))
                    edit_hours_zh = st.text_area("營業時間 (中文)", value=loc.get("hours_zh", ""), height=100)
                    edit_hours_en = st.text_area("Hours (English) / 營業時間", value=loc.get("hours_en", ""), height=100)
                    edit_map = st.text_area("地圖嵌入 / Map Embed", value=loc.get("map_embed", ""))
                    saved = st.form_submit_button("更新")
                if saved:
                    update_contact_location(
                        loc["id"],
                        edit_store_zh,
                        edit_store_en,
                        edit_address_zh,
                        edit_address_en,
                        edit_phone,
                        edit_hours_zh,
                        edit_hours_en,
                        edit_map,
                    )
                    st.success("已更新")
                    st.rerun()
            col_a, col_b, col_c, col_d = st.columns(4, gap="small")
            with col_a:
                if st.button("↑", key=f"loc_up_{loc['id']}"):
                    update_location_sort(loc["id"], "up")
                    st.rerun()
            with col_b:
                if st.button("↓", key=f"loc_down_{loc['id']}"):
                    update_location_sort(loc["id"], "down")
                    st.rerun()
            with col_c:
                if st.button("設為主店", key=f"loc_primary_{loc['id']}"):
                    set_primary_location(loc["id"])
                    st.rerun()
            with col_d:
                if st.button(t("admin_delete", lang), key=f"del_loc_{loc['id']}"):
                    delete_contact_location(loc["id"])
                    st.rerun()

    with tabs[4]:
        st.markdown("<div class='section-sub'>" + t("admin_messages", lang) + "</div>", unsafe_allow_html=True)
        for msg in list_messages():
            st.markdown(
                f"<div class='card'><div class='card-title'>{msg['user_name']}</div><div class='card-body'>{msg['content']}</div></div>",
                unsafe_allow_html=True,
            )
            if st.button(t("admin_delete", lang), key=f"del_msg_{msg['id']}"):
                delete_message(msg["id"])
                st.rerun()

    with tabs[5]:
        st.markdown("<div class='section-sub'>會員管理 / Members</div>", unsafe_allow_html=True)
        for user in list_users():
            st.markdown(
                f"<div class='card'><div class='card-title'>{user['username']}</div>"
                f"<div class='card-body'>姓名: {user.get('name','')}</div>"
                f"<div class='card-body'>Email: {user.get('email','')}</div>"
                f"<div class='card-body'>角色: {user.get('role','')}</div></div>",
                unsafe_allow_html=True,
            )
            if user["role"] != "admin":
                if st.button("刪除 / Delete", key=f"del_user_{user['id']}"):
                    delete_user(user["id"])
                    st.rerun()


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;600&family=Noto+Serif+TC:wght@400;600&family=Shadows+Into+Light&display=swap');
        :root {
            --sun-orange: #ffb266;
            --soft-orange: #ffd1c4;
            --leaf-green: #9ac59a;
            --cream: #fff5f0;
            --deep: #3b2f2a;
            --blush: #ffe3da;
            --blush-strong: #ffd3c7;
        }
        html, body, [class*="css"]  {
            font-family: "Noto Serif TC", "Comfortaa", serif;
            background: linear-gradient(180deg, var(--blush) 0%, #fff7f4 55%, #fff3ea 100%);
            color: var(--deep);
        }
        div[data-testid="stApp"] {
            background: linear-gradient(180deg, var(--blush) 0%, #fff7f4 55%, #fff3ea 100%);
        }
        section.main {
            background: transparent;
        }
        .block-container::before {
            content: "";
            position: fixed;
            inset: -20%;
            background: radial-gradient(circle at 20% 20%, rgba(255, 227, 218, 0.8), transparent 40%),
                        radial-gradient(circle at 80% 10%, rgba(255, 238, 232, 0.7), transparent 45%),
                        radial-gradient(circle at 50% 80%, rgba(255, 220, 210, 0.6), transparent 50%);
            filter: blur(24px);
            opacity: 0.85;
            z-index: 0;
            pointer-events: none;
        }
        .block-container > div {
            position: relative;
            z-index: 1;
        }
        .block-container {
            padding-top: 3.6rem;
        }
        .brand {
            font-size: 4.2rem;
            font-weight: 600;
            letter-spacing: 1px;
            font-family: "Shadows Into Light", "Noto Serif TC", serif;
            color: #e36a4e;
            background: linear-gradient(90deg, #ff8b5e, #ffb07a, #ff7a6a);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 2px 10px rgba(255, 181, 160, 0.35);
            cursor: pointer;
            animation: floatIn 9s ease-in-out infinite;
        }
        .brand-link {
            font-size: 4.2rem;
            font-weight: 600;
            letter-spacing: 1px;
            font-family: "Shadows Into Light", "Noto Serif TC", serif;
            color: #e36a4e;
            background: linear-gradient(90deg, #ff8b5e, #ffb07a, #ff7a6a);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            text-decoration: none;
            text-shadow: 0 2px 10px rgba(255, 181, 160, 0.35);
            display: inline-block;
            animation: floatIn 9s ease-in-out infinite;
        }
        .brand-link:hover {
            filter: brightness(0.95);
        }
        .tagline {
            color: #6c5e57;
            margin-top: 0.2rem;
            font-family: "Shadows Into Light", "Noto Serif TC", serif;
        }
        .section-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin: 1rem 0 0.6rem 0;
            color: #4a2f28;
        }
        .section-sub {
            margin-bottom: 0.8rem;
            color: #5a4a44;
        }
        .card-body {
            color: #5a4a44;
        }
        .card-title {
            color: #4a2f28;
        }
        .body-text {
            color: #5a4a44;
        }
        .stMarkdown, .stText, .stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label {
            color: #5a4a44;
        }
        .stMarkdown p, .stMarkdown span, .stMarkdown li {
            color: #5a4a44;
        }
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown span,
        section[data-testid="stSidebar"] label {
            color: #ffffff !important;
        }
        @keyframes floatIn {
            0% { transform: translateY(0px) scale(1); }
            50% { transform: translateY(-1.5px) scale(1.01); }
            100% { transform: translateY(0px) scale(1); }
        }
        .top-nav {
            background: #efefef;
            padding: 0.4rem 0.6rem;
            border-radius: 14px;
            display: flex;
            gap: 0.5rem;
            flex-wrap: nowrap;
            overflow-x: auto;
            margin-top: 0.6rem;
        }
        .nav-pill {
            background: #f7f7f7;
            color: #b3532b;
            padding: 0.35rem 0.8rem;
            border-radius: 999px;
            text-decoration: none;
            font-weight: 600;
            white-space: nowrap;
            border: 1px solid #e0e0e0;
        }
        .nav-pill:hover {
            background: #f0f0f0;
        }
        .stButton > button {
            background: #efefef;
            color: #b3532b;
            border: 1px solid #e0e0e0;
            border-radius: 999px;
            font-weight: 600;
            white-space: nowrap;
            padding: 0.55rem 1.6rem;
            font-size: clamp(1.0rem, 1.1vw + 0.4rem, 1.6rem);
            line-height: 1.1;
            box-sizing: border-box;
            min-width: 0;
            text-align: center;
        }
        .stButton > button:hover {
            background: #f0f0f0;
        }
        .stTabs [data-baseweb="tab-list"] button {
            color: #5a5a5a !important;
            font-size: 1.25rem !important;
            font-weight: 600;
        }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
            color: #4f4f4f !important;
        }
        details summary {
            color: #5a5a5a !important;
            font-weight: 600;
        }
        .login-pill {
            display: inline-block;
            background: #efefef;
            color: #b3532b;
            padding: 0.55rem 1.4rem;
            border-radius: 14px;
            text-decoration: none;
            font-weight: 600;
            border: 1px solid #e0e0e0;
        }
        .icon-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
        }
        .icon-card {
            background: #f7f7f7;
            color: #b3532b;
            padding: 0.9rem 1rem;
            border-radius: 16px;
            text-decoration: none;
            font-weight: 600;
            text-align: center;
            border: 1px solid #e0e0e0;
            box-shadow: 0 6px 16px rgba(0,0,0,0.05);
        }
        .icon-card:hover {
            background: #f0f0f0;
        }
        .pw-hint {
            color: #e85a3a;
            font-size: 14px;
            font-weight: 600;
            margin-top: 0.4rem;
        }
        .card {
            background: #fffdfb;
            border-radius: 16px;
            padding: 0.9rem 1rem;
            box-shadow: 0 10px 24px rgba(255, 179, 162, 0.22);
            border: 1px solid #ffe6dc;
            margin-bottom: 0.7rem;
        }
        .card-title {
            font-weight: 600;
            margin-bottom: 0.3rem;
        }
        .placeholder {
            background: repeating-linear-gradient(
                45deg,
                #ffe9e1,
                #ffe9e1 10px,
                #ffefe8 10px,
                #ffefe8 20px
            );
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            color: #8c7a72;
        }
        .product-card {
            background: #fffdfb;
            border-radius: 18px;
            padding: 1rem;
            box-shadow: 0 14px 30px rgba(255, 178, 162, 0.28);
            border: 1px solid #ffe6dc;
            margin-bottom: 1.2rem;
        }
        .badge {
            display: inline-block;
            background: var(--blush-strong);
            color: #6b4d3b;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.8rem;
            margin-top: 0.4rem;
        }
        .price {
            font-weight: 600;
            margin-top: 0.3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    # Allow Streamlit Cloud Secrets to drive bootstrap admin credentials.
    try:
        if "ADMIN_USERNAME" in st.secrets:
            os.environ["ADMIN_USERNAME"] = str(st.secrets["ADMIN_USERNAME"])
        if "ADMIN_PASSWORD" in st.secrets:
            os.environ["ADMIN_PASSWORD"] = str(st.secrets["ADMIN_PASSWORD"])
    except Exception:
        pass
    init_db()
    apply_theme()

    lang = st.sidebar.selectbox("語言 / Language", ["zh", "en"], index=0)

    if "page" not in st.session_state:
        st.session_state["page"] = "home"

    page = st.session_state["page"]

    if page == "home":
        render_home(lang)
    elif page == "products":
        render_products(lang)
    elif page == "messages":
        render_messages(lang)
    elif page == "find_us":
        render_find_us(lang)
    elif page == "member":
        render_member(lang)
    # cart page removed
    elif page == "media":
        render_media(lang)
    elif page == "admin":
        render_admin(lang)
    else:
        render_home(lang)


if __name__ == "__main__":
    main()
