import telebot
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import time
import json
import re
from datetime import datetime

# ==================== تنظیمات ====================
BOT_TOKEN = "8423981755:AAFaEYzOefEaxDiuyvKKyyTJzlhDXWSqyRw"
ADMIN_IDS = [8916314219]  # آیدی عددی ادمین‌ها
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== دیتابیس ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('/tmp/whites_panel.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        # جدول کانفیگ‌ها
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                link TEXT UNIQUE,
                category TEXT DEFAULT 'general',
                added_by INTEGER,
                added_at INTEGER,
                is_active INTEGER DEFAULT 1,
                description TEXT DEFAULT ''
            )
        ''')
        
        # جدول دسته‌بندی‌ها
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                color TEXT DEFAULT '#3498db',
                icon TEXT DEFAULT '📁'
            )
        ''')
        
        # جدول لاگ
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                user_id INTEGER,
                username TEXT,
                timestamp INTEGER,
                details TEXT
            )
        ''')
        
        self.conn.commit()
        
        # دسته‌بندی پیش‌فرض
        self.cursor.execute("INSERT OR IGNORE INTO categories (name, color, icon) VALUES ('general', '#3498db', '📁')")
        self.cursor.execute("INSERT OR IGNORE INTO categories (name, color, icon) VALUES ('ایران', '#2ecc71', '🇮🇷')")
        self.cursor.execute("INSERT OR IGNORE INTO categories (name, color, icon) VALUES ('آلمان', '#f1c40f', '🇩🇪')")
        self.cursor.execute("INSERT OR IGNORE INTO categories (name, color, icon) VALUES ('انگلیس', '#e74c3c', '🇬🇧')")
        self.conn.commit()
    
    # ========== کانفیگ‌ها ==========
    def add_config(self, name, link, added_by, category='general', description=''):
        try:
            self.cursor.execute(
                "INSERT INTO configs (name, link, added_by, added_at, category, description) VALUES (?, ?, ?, ?, ?, ?)",
                (name, link, added_by, int(time.time()), category, description)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_all_configs(self, category=None, active_only=True):
        query = "SELECT id, name, link, category, description FROM configs"
        params = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        if active_only and not category:
            query += " WHERE is_active = 1"
        elif active_only and category:
            query += " AND is_active = 1"
        self.cursor.execute(query, params)
        return self.cursor.fetchall()
    
    def get_config(self, config_id):
        self.cursor.execute("SELECT id, name, link, category, description FROM configs WHERE id = ?", (config_id,))
        return self.cursor.fetchone()
    
    def update_config(self, config_id, name=None, link=None, category=None, description=None, is_active=None):
        updates = []
        params = []
        if name:
            updates.append("name = ?")
            params.append(name)
        if link:
            updates.append("link = ?")
            params.append(link)
        if category:
            updates.append("category = ?")
            params.append(category)
        if description:
            updates.append("description = ?")
            params.append(description)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        
        if not updates:
            return False
        
        params.append(config_id)
        self.cursor.execute(f"UPDATE configs SET {', '.join(updates)} WHERE id = ?", params)
        self.conn.commit()
        return True
    
    def delete_config(self, config_id):
        self.cursor.execute("DELETE FROM configs WHERE id = ?", (config_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def search_configs(self, query):
        self.cursor.execute(
            "SELECT id, name, link, category, description FROM configs WHERE name LIKE ? OR category LIKE ? OR description LIKE ?",
            (f'%{query}%', f'%{query}%', f'%{query}%')
        )
        return self.cursor.fetchall()
    
    def get_categories(self):
        self.cursor.execute("SELECT name, color, icon FROM categories")
        return self.cursor.fetchall()
    
    def get_category_count(self, category):
        self.cursor.execute("SELECT COUNT(*) FROM configs WHERE category = ? AND is_active = 1", (category,))
        return self.cursor.fetchone()[0]
    
    def get_total_configs(self):
        self.cursor.execute("SELECT COUNT(*) FROM configs WHERE is_active = 1")
        return self.cursor.fetchone()[0]
    
    # ========== لاگ ==========
    def add_log(self, action, user_id, username, details=''):
        self.cursor.execute(
            "INSERT INTO logs (action, user_id, username, timestamp, details) VALUES (?, ?, ?, ?, ?)",
            (action, user_id, username, int(time.time()), details)
        )
        self.conn.commit()
    
    def get_logs(self, limit=50):
        self.cursor.execute("SELECT action, username, timestamp, details FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        return self.cursor.fetchall()
    
    # ========== خروجی JSON ==========
    def export_json(self):
        configs = self.get_all_configs(active_only=False)
        data = []
        for cid, name, link, category, description in configs:
            data.append({
                'id': cid,
                'name': name,
                'link': link,
                'category': category,
                'description': description
            })
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def import_json(self, json_data):
        try:
            data = json.loads(json_data)
            count = 0
            for item in data:
                if self.add_config(item['name'], item['link'], 0, item.get('category', 'general'), item.get('description', '')):
                    count += 1
            return count
        except:
            return -1
    
    def close(self):
        self.conn.close()

db = Database()

# ==================== منوی اصلی (رنگی فارسی فوق‌لوکس) ====================
def get_main_menu(user_id):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)
    
    if is_admin(user_id):
        # ردیف ۱
        btn_add = KeyboardButton("➕ افزودن کانفیگ", style="success")        # 🟢 سبز
        btn_delete = KeyboardButton("❌ حذف کانفیگ", style="danger")          # 🔴 قرمز
        
        # ردیف ۲
        btn_list = KeyboardButton("📋 لیست کانفیگ‌ها", style="primary")      # 🔵 آبی
        btn_get = KeyboardButton("📤 دریافت کانفیگ", style="primary")         # 🔵 آبی
        
        # ردیف ۳
        btn_edit = KeyboardButton("✏️ ویرایش کانفیگ", style="yellow")        # 🟡 زرد
        btn_search = KeyboardButton("🔍 جستجوی پیشرفته", style="orange")     # 🟠 نارنجی
        
        # ردیف ۴
        btn_cat = KeyboardButton("📂 مدیریت دسته‌بندی", style="purple")      # 🟣 بنفش
        btn_stats = KeyboardButton("📊 آمار و نمودار", style="primary")      # 🔵 آبی
        
        # ردیف ۵
        btn_backup = KeyboardButton("💾 پشتیبان‌گیری", style="yellow")       # 🟡 زرد
        btn_logs = KeyboardButton("📜 گزارش‌ها", style="primary")            # 🔵 آبی
        
        # ردیف ۶
        btn_help = KeyboardButton("❓ راهنمای کامل", style="primary")        # 🔵 آبی
        
        markup.add(btn_add, btn_delete)
        markup.add(btn_list, btn_get)
        markup.add(btn_edit, btn_search)
        markup.add(btn_cat, btn_stats)
        markup.add(btn_backup, btn_logs)
        markup.add(btn_help)
    else:
        btn_list = KeyboardButton("📋 لیست کانفیگ‌ها", style="primary")
        btn_get = KeyboardButton("📤 دریافت کانفیگ", style="primary")
        btn_search = KeyboardButton("🔍 جستجو", style="primary")
        btn_help = KeyboardButton("❓ راهنما", style="primary")
        markup.add(btn_list, btn_get)
        markup.add(btn_search, btn_help)
    
    return markup

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ==================== پیام خوش‌آمدگویی ====================
@bot.message_handler(commands=['start', 'help'])
def start_command(message: Message):
    user_id = message.from_user.id
    markup = get_main_menu(user_id)
    
    text = f"""
🌟 <b>پنل وایت‌دی‌ان‌اس (Whites DNS) - نسخه لوکس</b>

سلام {message.from_user.first_name} 👋
به پنل فوق‌پیشرفته مدیریت کانفیگ‌های <b>StormDNS</b> خوش آمدید.

🔹 <b>امکانات بی‌نظیر:</b>
• مدیریت کانفیگ‌ها (افزودن، حذف، ویرایش)
• دسته‌بندی هوشمند با رنگ‌بندی
• جستجوی پیشرفته
• آمار و گزارش‌گیری
• پشتیبان‌گیری JSON
• دکمه‌های رنگی (سبز، قرمز، آبی، زرد، بنفش، نارنجی)
• رابط کاربری لوکس و حرفه‌ای

🔸 <b>نحوه استفاده:</b>
از دکمه‌های زیر برای مدیریت استفاده کنید.

⚡ <i>پنل شما آماده است! لذت ببرید 🚀</i>
"""
    bot.reply_to(message, text, reply_markup=markup)

# ==================== افزودن کانفیگ ====================
@bot.message_handler(func=lambda m: m.text == "➕ افزودن کانفیگ")
def add_config_menu(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    text = """
➕ <b>افزودن کانفیگ جدید</b>

📌 <b>فرمت ورود:</b>
<code>/addconfig نام | لینک | دسته‌بندی | توضیحات</code>

📌 <b>مثال کامل:</b>
<code>/addconfig ریزا | stormdns://... | ایران | سرور اصلی</code>

💡 <i>• دسته‌بندی و توضیحات اختیاری هستند.</i>
💡 <i>• اگر دسته‌بندی وارد نشود، در 'general' قرار می‌گیرد.</i>
💡 <i>• دسته‌بندی‌های موجود:</i>
"""
    categories = db.get_categories()
    for cat, color, icon in categories:
        text += f"   {icon} {cat}\n"
    
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

@bot.message_handler(commands=['addconfig'])
def add_config_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً اطلاعات کامل را وارد کنید.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    parts = [p.strip() for p in args[1].split('|')]
    if len(parts) < 2:
        bot.reply_to(message, "❌ حداقل نام و لینک را وارد کنید. (با '|' جدا کنید)", reply_markup=get_main_menu(message.from_user.id))
        return
    
    name = parts[0]
    link = parts[1]
    category = parts[2] if len(parts) > 2 else 'general'
    description = parts[3] if len(parts) > 3 else ''
    
    if not link.startswith('stormdns://'):
        bot.reply_to(message, "❌ لینک باید با <code>stormdns://</code> شروع شود.", parse_mode='HTML', reply_markup=get_main_menu(message.from_user.id))
        return
    
    if db.add_config(name, link, message.from_user.id, category, description):
        db.add_log('add_config', message.from_user.id, message.from_user.username, f'{name} - {category}')
        bot.reply_to(message, f"✅ کانفیگ <b>{name}</b> با موفقیت افزوده شد.\n📂 دسته: {category}\n📝 توضیحات: {description or 'ندارد'}", reply_markup=get_main_menu(message.from_user.id))
    else:
        bot.reply_to(message, "❌ این لینک قبلاً ثبت شده است.", reply_markup=get_main_menu(message.from_user.id))

# ==================== لیست کانفیگ‌ها (با دسته‌بندی) ====================
@bot.message_handler(func=lambda m: m.text == "📋 لیست کانفیگ‌ها")
def list_configs(message: Message):
    categories = db.get_categories()
    if not categories:
        bot.reply_to(message, "📭 هیچ کانفیگی وجود ندارد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    for cat, color, icon in categories:
        count = db.get_category_count(cat)
        btn = InlineKeyboardButton(f"{icon} {cat} ({count})", callback_data=f"list_{cat}")
        markup.add(btn)
    
    btn_all = InlineKeyboardButton("📋 همه کانفیگ‌ها", callback_data="list_all")
    markup.add(btn_all)
    
    bot.reply_to(message, "📂 <b>انتخاب دسته‌بندی:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('list_'))
def show_configs(call):
    category = call.data.split('_')[1] if call.data != 'list_all' else None
    configs = db.get_all_configs(category)
    
    if not configs:
        bot.answer_callback_query(call.id, "📭 هیچ کانفیگی در این دسته وجود ندارد!")
        return
    
    text = "📋 <b>لیست کانفیگ‌ها</b>\n\n"
    for cid, name, link, cat, desc in configs:
        text += f"🔹 <b>{name}</b>\n"
        text += f"   📂 {cat}\n"
        text += f"   🆔 {cid}\n"
        if desc:
            text += f"   📝 {desc}\n"
        text += f"   🔗 <code>{link[:50]}...</code>\n\n"
    
    bot.send_message(call.message.chat.id, text, parse_mode='HTML')
    bot.answer_callback_query(call.id, "✅ لیست ارسال شد!")

# ==================== دریافت کانفیگ ====================
@bot.message_handler(func=lambda m: m.text == "📤 دریافت کانفیگ")
def get_config_menu(message: Message):
    markup = InlineKeyboardMarkup(row_width=1)
    configs = db.get_all_configs()
    
    if not configs:
        bot.reply_to(message, "📭 هیچ کانفیگی موجود نیست.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    for cid, name, link, category, desc in configs:
        btn = InlineKeyboardButton(f"📌 {name} ({category})", callback_data=f"get_{cid}")
        markup.add(btn)
    
    bot.reply_to(message, "🔽 یکی از کانفیگ‌های زیر را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('get_'))
def send_config(call):
    config_id = int(call.data.split('_')[1])
    config = db.get_config(config_id)
    if not config:
        bot.answer_callback_query(call.id, "❌ کانفیگ پیدا نشد!")
        return
    
    cid, name, link, category, description = config
    text = f"""
🌟 <b>کانفیگ وایت‌دی‌ان‌اس</b>

📌 <b>نام:</b> {name}
📂 <b>دسته:</b> {category}
🆔 <b>شناسه:</b> {cid}
📝 <b>توضیحات:</b> {description or 'ندارد'}

🔗 <b>لینک:</b>
<code>{link}</code>

💡 <i>برای استفاده، لینک را کپی کنید.</i>
"""
    bot.send_message(call.message.chat.id, text, parse_mode='HTML')
    db.add_log('get_config', call.from_user.id, call.from_user.username, name)
    bot.answer_callback_query(call.id, "✅ کانفیگ ارسال شد!")

# ==================== ویرایش کانفیگ ====================
@bot.message_handler(func=lambda m: m.text == "✏️ ویرایش کانفیگ")
def edit_config_menu(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    configs = db.get_all_configs()
    
    if not configs:
        bot.reply_to(message, "📭 هیچ کانفیگی برای ویرایش وجود ندارد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    for cid, name, link, category, desc in configs:
        btn = InlineKeyboardButton(f"✏️ {name}", callback_data=f"edit_{cid}")
        markup.add(btn)
    
    bot.reply_to(message, "✏️ کانفیگ مورد نظر را برای ویرایش انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_config_form(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
        return
    
    config_id = int(call.data.split('_')[1])
    config = db.get_config(config_id)
    if not config:
        bot.answer_callback_query(call.id, "❌ کانفیگ پیدا نشد!")
        return
    
    cid, name, link, category, description = config
    
    text = f"""
✏️ <b>ویرایش کانفیگ #{cid}</b>

📌 <b>نام فعلی:</b> {name}
📂 <b>دسته فعلی:</b> {category}
📝 <b>توضیحات فعلی:</b> {description or 'ندارد'}

🔹 <b>دستورات ویرایش:</b>
/editname {cid} نام جدید
/editcategory {cid} دسته جدید
/editdesc {cid} توضیحات جدید
/edittoggle {cid} (فعال/غیرفعال)

💡 <i>مثال: /editname 5 سرور جدید</i>
"""
    bot.send_message(call.message.chat.id, text, parse_mode='HTML')
    bot.answer_callback_query(call.id, "✅ دستورات ویرایش ارسال شد!")

@bot.message_handler(commands=['editname', 'editcategory', 'editdesc', 'edittoggle'])
def edit_config_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً شناسه و مقدار جدید را وارد کنید.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    cmd = args[0]
    try:
        config_id = int(args[1])
    except:
        bot.reply_to(message, "❌ شناسه باید عدد باشد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    config = db.get_config(config_id)
    if not config:
        bot.reply_to(message, "❌ کانفیگ پیدا نشد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    if cmd == '/edittoggle':
        new_status = 0 if config[4] else 1  # is_active
        db.update_config(config_id, is_active=new_status)
        bot.reply_to(message, f"✅ وضعیت کانفیگ #{config_id} به {'فعال' if new_status else 'غیرفعال'} تغییر کرد.", reply_markup=get_main_menu(message.from_user.id))
        db.add_log('toggle_config', message.from_user.id, message.from_user.username, f'#{config_id} -> {new_status}')
        return
    
    if len(args) < 3:
        bot.reply_to(message, "❌ لطفاً مقدار جدید را وارد کنید.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    new_value = args[2]
    
    if cmd == '/editname':
        db.update_config(config_id, name=new_value)
        bot.reply_to(message, f"✅ نام کانفیگ #{config_id} به '{new_value}' تغییر کرد.", reply_markup=get_main_menu(message.from_user.id))
    elif cmd == '/editcategory':
        db.update_config(config_id, category=new_value)
        bot.reply_to(message, f"✅ دسته کانفیگ #{config_id} به '{new_value}' تغییر کرد.", reply_markup=get_main_menu(message.from_user.id))
    elif cmd == '/editdesc':
        db.update_config(config_id, description=new_value)
        bot.reply_to(message, f"✅ توضیحات کانفیگ #{config_id} به '{new_value}' تغییر کرد.", reply_markup=get_main_menu(message.from_user.id))
    
    db.add_log('edit_config', message.from_user.id, message.from_user.username, f'#{config_id} -> {cmd}: {new_value}')

# ==================== حذف کانفیگ ====================
@bot.message_handler(func=lambda m: m.text == "❌ حذف کانفیگ")
def delete_config_menu(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    configs = db.get_all_configs()
    
    if not configs:
        bot.reply_to(message, "📭 هیچ کانفیگی برای حذف وجود ندارد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    for cid, name, link, category, desc in configs:
        btn = InlineKeyboardButton(f"❌ {name}", callback_data=f"del_{cid}")
        markup.add(btn)
    
    bot.reply_to(message, "⚠️ کانفیگ مورد نظر را برای حذف انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_config(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
        return
    
    config_id = int(call.data.split('_')[1])
    config = db.get_config(config_id)
    if config and db.delete_config(config_id):
        db.add_log('delete_config', call.from_user.id, call.from_user.username, config[1])
        bot.answer_callback_query(call.id, "✅ کانفیگ با موفقیت حذف شد!")
        bot.edit_message_text("✅ کانفیگ حذف شد.", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "❌ خطا در حذف!")

# ==================== جستجوی پیشرفته ====================
@bot.message_handler(func=lambda m: m.text == "🔍 جستجوی پیشرفته")
def search_menu(message: Message):
    text = """
🔍 <b>جستجوی پیشرفته</b>

با دستور زیر می‌توانید در کانفیگ‌ها جستجو کنید:

<code>/search کلمه مورد نظر</code>

🔹 <b>قابلیت‌ها:</b>
• جستجو در نام
• جستجو در دسته‌بندی
• جستجو در توضیحات

💡 <i>مثال: /search ایران</i>
"""
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

@bot.message_handler(commands=['search'])
def search_configs(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً کلمه مورد جستجو را وارد کنید.\nمثال: /search ایران", reply_markup=get_main_menu(message.from_user.id))
        return
    
    query = args[1]
    results = db.search_configs(query)
    
    if not results:
        bot.reply_to(message, f"🔍 هیچ نتیجه‌ای برای '{query}' پیدا نشد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    text = f"🔍 <b>نتایج جستجو برای '{query}'</b>\n\n"
    for cid, name, link, category, desc in results[:20]:
        text += f"🔹 <b>{name}</b>\n"
        text += f"   📂 {category}\n"
        text += f"   🆔 {cid}\n"
        text += f"   🔗 <code>{link[:40]}...</code>\n\n"
    
    if len(results) > 20:
        text += f"\n... و {len(results) - 20} نتیجه دیگر"
    
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

# ==================== مدیریت دسته‌بندی ====================
@bot.message_handler(func=lambda m: m.text == "📂 مدیریت دسته‌بندی")
def category_management(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    text = """
📂 <b>مدیریت دسته‌بندی</b>

🔹 <b>دستورات:</b>
/addcategory نام - افزودن دسته جدید
/removecategory نام - حذف دسته
/listcategories - لیست دسته‌بندی‌ها

💡 <i>مثال: /addcategory آمریکا</i>
"""
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

@bot.message_handler(commands=['addcategory'])
def add_category(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً نام دسته را وارد کنید.\nمثال: /addcategory آمریکا", reply_markup=get_main_menu(message.from_user.id))
        return
    
    try:
        db.cursor.execute("INSERT INTO categories (name, color, icon) VALUES (?, '#3498db', '📁')", (args[1],))
        db.conn.commit()
        bot.reply_to(message, f"✅ دسته '{args[1]}' با موفقیت اضافه شد.", reply_markup=get_main_menu(message.from_user.id))
    except sqlite3.IntegrityError:
        bot.reply_to(message, f"❌ دسته '{args[1]}' قبلاً وجود دارد.", reply_markup=get_main_menu(message.from_user.id))

@bot.message_handler(commands=['removecategory'])
def remove_category(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً نام دسته را وارد کنید.\nمثال: /removecategory آمریکا", reply_markup=get_main_menu(message.from_user.id))
        return
    
    db.cursor.execute("DELETE FROM categories WHERE name = ?", (args[1],))
    db.conn.commit()
    # تغییر دسته کانفیگ‌ها به general
    db.cursor.execute("UPDATE configs SET category = 'general' WHERE category = ?", (args[1],))
    db.conn.commit()
    bot.reply_to(message, f"✅ دسته '{args[1]}' حذف شد و کانفیگ‌های آن به general منتقل شدند.", reply_markup=get_main_menu(message.from_user.id))

@bot.message_handler(commands=['listcategories'])
def list_categories(message: Message):
    categories = db.get_categories()
    if not categories:
        bot.reply_to(message, "📭 هیچ دسته‌بندی وجود ندارد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    text = "📂 <b>دسته‌بندی‌ها</b>\n\n"
    for name, color, icon in categories:
        count = db.get_category_count(name)
        text += f"{icon} <b>{name}</b> - {count} کانفیگ\n"
    
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

# ==================== آمار و نمودار ====================
@bot.message_handler(func=lambda m: m.text == "📊 آمار و نمودار")
def stats_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    total = db.get_total_configs()
    categories = db.get_categories()
    
    text = f"""
📊 <b>آمار پنل وایت‌دی‌ان‌اس</b>

🔹 <b>آمار کلی:</b>
• تعداد کل کانفیگ‌ها: {total}

📂 <b>توزیع دسته‌بندی:</b>
"""
    for name, color, icon in categories:
        count = db.get_category_count(name)
        percentage = (count / total * 100) if total > 0 else 0
        bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
        text += f"{icon} {name}: {count} ({percentage:.1f}%)\n"
        text += f"   {bar}\n"
    
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

# ==================== پشتیبان‌گیری ====================
@bot.message_handler(func=lambda m: m.text == "💾 پشتیبان‌گیری")
def backup_menu(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    btn_export = InlineKeyboardButton("📤 خروجی JSON", callback_data="export_json")
    btn_import = InlineKeyboardButton("📥 ورودی JSON", callback_data="import_json")
    markup.add(btn_export, btn_import)
    
    bot.reply_to(message, "💾 <b>پشتیبان‌گیری</b>\n\nعملیات مورد نظر را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "export_json")
def export_json(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
        return
    
    json_data = db.export_json()
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # ارسال فایل
    import io
    file_obj = io.BytesIO(json_data.encode('utf-8'))
    file_obj.name = filename
    bot.send_document(call.message.chat.id, file_obj, caption="📤 پشتیبان‌گیری با موفقیت انجام شد!")
    bot.answer_callback_query(call.id, "✅ فایل ارسال شد!")

@bot.callback_query_handler(func=lambda call: call.data == "import_json")
def import_json_prompt(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
        return
    
    bot.send_message(call.message.chat.id, "📥 لطفاً فایل JSON را با دستور /import ارسال کنید.\nمثال: /import (به‌عنوان ریپلای به فایل)")
    bot.answer_callback_query(call.id, "✅ دستورالعمل ارسال شد!")

@bot.message_handler(commands=['import'])
def import_json_file(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(message, "❌ لطفاً فایل JSON را به‌عنوان ریپلای به این پیام ارسال کنید.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    try:
        file_info = bot.get_file(message.reply_to_message.document.file_id)
        file_content = bot.download_file(file_info.file_path)
        json_data = file_content.decode('utf-8')
        
        count = db.import_json(json_data)
        if count >= 0:
            db.add_log('import_json', message.from_user.id, message.from_user.username, f'{count} configs imported')
            bot.reply_to(message, f"✅ {count} کانفیگ با موفقیت وارد شد!", reply_markup=get_main_menu(message.from_user.id))
        else:
            bot.reply_to(message, "❌ فرمت فایل معتبر نیست.", reply_markup=get_main_menu(message.from_user.id))
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}", reply_markup=get_main_menu(message.from_user.id))

# ==================== گزارش‌ها ====================
@bot.message_handler(func=lambda m: m.text == "📜 گزارش‌ها")
def logs_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    logs = db.get_logs(20)
    if not logs:
        bot.reply_to(message, "📭 هیچ گزارشی ثبت نشده است.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    text = "📜 <b>گزارش‌های اخیر</b>\n\n"
    for action, username, timestamp, details in logs:
        time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M %Y/%m/%d')
        text += f"🔹 {action} - {username or 'سیستم'}\n"
        text += f"   🕐 {time_str}\n"
        if details:
            text += f"   📝 {details}\n"
        text += "\n"
    
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

# ==================== راهنمای کامل ====================
@bot.message_handler(func=lambda m: m.text == "❓ راهنمای کامل")
def full_help(message: Message):
    text = """
❓ <b>راهنمای کامل پنل وایت‌دی‌ان‌اس</b>

🔹 <b>دستورات اصلی:</b>
/start - شروع و نمایش منو
/help - این پیام

🔹 <b>مدیریت کانفیگ‌ها:</b>
/addconfig نام | لینک | دسته | توضیحات - افزودن کانفیگ
/search کلمه - جستجوی کانفیگ‌ها

🔹 <b>مدیریت دسته‌بندی:</b>
/addcategory نام - افزودن دسته جدید
/removecategory نام - حذف دسته
/listcategories - لیست دسته‌بندی‌ها

🔹 <b>ویرایش کانفیگ‌ها:</b>
/editname شناسه نام جدید
/editcategory شناسه دسته جدید
/editdesc شناسه توضیحات جدید
/edittoggle شناسه - فعال/غیرفعال

🔹 <b>پشتیبان‌گیری:</b>
/import - ورودی JSON (ریپلای به فایل)

🔹 <b>دکمه‌های منو:</b>
• افزودن کانفیگ (🟢 سبز)
• حذف کانفیگ (🔴 قرمز)
• لیست کانفیگ‌ها (🔵 آبی)
• دریافت کانفیگ (🔵 آبی)
• ویرایش کانفیگ (🟡 زرد)
• جستجوی پیشرفته (🟠 نارنجی)
• مدیریت دسته‌بندی (🟣 بنفش)
• آمار و نمودار (🔵 آبی)
• پشتیبان‌گیری (🟡 زرد)
• گزارش‌ها (🔵 آبی)

💡 <i>پنل شما آماده است! لذت ببرید 🚀</i>
"""
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

# ==================== مدیریت خطا ====================
@bot.message_handler(func=lambda m: True)
def fallback(message: Message):
    bot.reply_to(message, "❓ دستور ناشناخته. از دکمه‌های منو استفاده کنید.", reply_markup=get_main_menu(message.from_user.id))

# ==================== راه‌اندازی ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🌟 پنل وایت‌دی‌ان‌اس (نسخه فوق‌پیشرفته لوکس)")
    print("=" * 60)
    print("✅ ربات راه‌اندازی شد.")
    print("👑 ادمین‌ها:", ADMIN_IDS)
    print("🎨 رنگ‌ها: سبز | قرمز | آبی | زرد | بنفش | نارنجی")
    print("📌 برای شروع از /start استفاده کنید.")
    print("=" * 60)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"خطا در پولینگ: {e}")
            time.sleep(5)
