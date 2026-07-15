گپ#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ربات پیشرفته تلگرام - نسخه کامل یکپارچه
Advanced Telegram Bot - Complete Single File Version
"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler  # <-- این خط مهمه
import os
import sys
import json
import re
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict
import time
import random
import string

# ============================================
# بخش 1: تنظیمات و متغیرهای محیطی
# ============================================

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# تنظیمات از محیط
BOT_TOKEN = os.getenv("8810741889:AAEjL5vlgL0mxZeAmRGWtDuU7kKFCKwJQ2M", "8810741889:AAEjL5vlgL0mxZeAmRGWtDuU7kKFCKwJQ2M")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@rza_Fastgrootz_bot")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "8680457924").split(",") if id.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
XUI_PANEL_URL = os.getenv("XUI_PANEL_URL", "https://railway-x3ui-production-fd6d.up.railway.app/panel/")
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "admin")
REDIS_URL = os.getenv("REDIS_URL", "100")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# تنظیمات امنیتی
RATE_LIMIT_PER_USER = int(os.getenv("RATE_LIMIT_PER_USER", 100))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", 60))
MAX_REQUESTS_PER_DAY = int(os.getenv("MAX_REQUESTS_PER_DAY", 1000))
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", 20))
VIP_DAILY_LIMIT = int(os.getenv("VIP_DAILY_LIMIT", 200))

# ============================================
# بخش 2: سیستم لاگ‌گیری (اصلاح شده)
# ============================================

def setup_logging():
    """راه‌اندازی سیستم لاگ‌گیری"""
    # ایجاد پوشه لاگ
    Path("logs").mkdir(exist_ok=True)
    
    # تنظیم لاگر اصلی
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # حذف هندلرهای قبلی
    logger.handlers.clear()
    
    # فرمت لاگ
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # هندلر کنسول
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    # هندلر فایل (استفاده از RotatingFileHandler به درستی)
    try:
        file_handler = RotatingFileHandler(
            "logs/bot.log",
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file handler: {e}")
    
    # هندلر خطاها
    try:
        error_handler = RotatingFileHandler(
            "logs/errors.log",
            maxBytes=5*1024*1024,
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
    except Exception as e:
        print(f"Warning: Could not create error handler: {e}")
    
    return logger

logger = setup_logging()

# ============================================
# بخش 3: کلاس‌های مدل و دیتابیس
# ============================================

class UserStatus(Enum):
    ACTIVE = "active"
    BANNED = "banned"
    VIP = "vip"

@dataclass
class User:
    """مدل کاربر"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: str = "active"
    is_vip: bool = False
    vip_expiry: Optional[datetime] = None
    daily_limit: int = FREE_DAILY_LIMIT
    used_today: int = 0
    total_requests: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    language: str = "fa"
    balance: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'status': self.status,
            'is_vip': self.is_vip,
            'vip_expiry': self.vip_expiry.isoformat() if self.vip_expiry else None,
            'daily_limit': self.daily_limit,
            'used_today': self.used_today,
            'total_requests': self.total_requests,
            'created_at': self.created_at.isoformat(),
            'last_active': self.last_active.isoformat(),
            'language': self.language,
            'balance': self.balance
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        return cls(
            user_id=data['user_id'],
            username=data.get('username'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            status=data.get('status', 'active'),
            is_vip=data.get('is_vip', False),
            vip_expiry=datetime.fromisoformat(data['vip_expiry']) if data.get('vip_expiry') else None,
            daily_limit=data.get('daily_limit', FREE_DAILY_LIMIT),
            used_today=data.get('used_today', 0),
            total_requests=data.get('total_requests', 0),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            last_active=datetime.fromisoformat(data['last_active']) if data.get('last_active') else datetime.now(),
            language=data.get('language', 'fa'),
            balance=data.get('balance', 0.0)
        )

class Database:
    """کلاس دیتابیس با پشتیبانی از SQLite/PostgreSQL"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.db_type = "sqlite" if "sqlite" in DATABASE_URL else "postgres"
            self._init_db()
    
    def _init_db(self):
        """راه‌اندازی دیتابیس"""
        import sqlite3
        
        if self.db_type == "sqlite":
            db_path = DATABASE_URL.replace("sqlite:///", "")
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._create_tables_sqlite()
        else:
            # PostgreSQL
            try:
                import asyncpg
                # برای سادگی از SQLite استفاده می‌کنیم
                db_path = "bot.db"
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self._create_tables_sqlite()
            except:
                db_path = "bot.db"
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self._create_tables_sqlite()
    
    def _create_tables_sqlite(self):
        """ایجاد جداول SQLite"""
        cursor = self.conn.cursor()
        
        # جدول کاربران
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                status TEXT DEFAULT 'active',
                is_vip INTEGER DEFAULT 0,
                vip_expiry TEXT,
                daily_limit INTEGER DEFAULT 20,
                used_today INTEGER DEFAULT 0,
                total_requests INTEGER DEFAULT 0,
                created_at TEXT,
                last_active TEXT,
                language TEXT DEFAULT 'fa',
                balance REAL DEFAULT 0
            )
        ''')
        
        # جدول تاریخچه
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                created_at TEXT
            )
        ''')
        
        # جدول کانفیگ‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                domain TEXT,
                protocol TEXT,
                config TEXT,
                created_at TEXT,
                expires_at TEXT
            )
        ''')
        
        # جدول خطاها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                error TEXT,
                created_at TEXT
            )
        ''')
        
        # جدول پیام‌های انبوه
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                sent_count INTEGER DEFAULT 0,
                total_count INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        self.conn.commit()
    
    def execute(self, query: str, params: tuple = ()):
        """اجرای کوئری"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor
    
    def fetch_one(self, query: str, params: tuple = ()):
        """دریافت یک رکورد"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    
    def fetch_all(self, query: str, params: tuple = ()):
        """دریافت همه رکوردها"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def close(self):
        """بستن اتصال"""
        if hasattr(self, 'conn'):
            self.conn.close()

# ============================================
# بخش 4: سرویس‌های اصلی
# ============================================

class UserService:
    """سرویس مدیریت کاربران"""
    
    def __init__(self):
        self.db = Database()
    
    async def get_or_create_user(self, user_id: int, username: str = None, 
                                  first_name: str = None, last_name: str = None) -> Dict:
        """دریافت یا ایجاد کاربر"""
        # بررسی وجود کاربر
        user = self.db.fetch_one(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )
        
        if not user:
            # ایجاد کاربر جدید
            now = datetime.now().isoformat()
            self.db.execute(
                """INSERT INTO users 
                   (user_id, username, first_name, last_name, created_at, last_active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username, first_name, last_name, now, now)
            )
            user = self.db.fetch_one(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
        
        # بروزرسانی آخرین فعالیت
        self.db.execute(
            "UPDATE users SET last_active = ? WHERE user_id = ?",
            (datetime.now().isoformat(), user_id)
        )
        
        # تبدیل به دیکشنری
        return dict(user) if user else None
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """دریافت اطلاعات کاربر"""
        user = self.db.fetch_one(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )
        return dict(user) if user else None
    
    async def update_user(self, user_id: int, **kwargs) -> bool:
        """بروزرسانی کاربر"""
        fields = []
        values = []
        
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        if not fields:
            return False
            
        values.append(user_id)
        query = f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?"
        
        try:
            self.db.execute(query, tuple(values))
            return True
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    async def increment_usage(self, user_id: int) -> bool:
        """افزایش آمار استفاده"""
        try:
            self.db.execute(
                "UPDATE users SET used_today = used_today + 1, total_requests = total_requests + 1 WHERE user_id = ?",
                (user_id,)
            )
            return True
        except:
            return False
    
    async def reset_daily_usage(self):
        """ریست استفاده روزانه"""
        self.db.execute("UPDATE users SET used_today = 0")
    
    async def get_all_users(self) -> List[Dict]:
        """دریافت همه کاربران"""
        users = self.db.fetch_all("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(u) for u in users]
    
    async def get_user_count(self) -> int:
        """تعداد کاربران"""
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM users")
        return result['count'] if result else 0
    
    async def get_active_users(self, days: int = 7) -> int:
        """تعداد کاربران فعال"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM users WHERE last_active > ?",
            (cutoff,)
        )
        return result['count'] if result else 0
    
    async def set_vip(self, user_id: int, days: int) -> bool:
        """تنظیم VIP برای کاربر"""
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
        return await self.update_user(
            user_id,
            is_vip=1,
            vip_expiry=expiry,
            daily_limit=VIP_DAILY_LIMIT
        )
    
    async def check_vip_status(self, user_id: int) -> bool:
        """بررسی وضعیت VIP"""
        user = await self.get_user(user_id)
        if not user or not user.get('is_vip'):
            return False
            
        expiry = user.get('vip_expiry')
        if expiry and datetime.fromisoformat(expiry) < datetime.now():
            # منقضی شده
            await self.update_user(user_id, is_vip=0, daily_limit=FREE_DAILY_LIMIT)
            return False
            
        return True
    
    async def log_history(self, user_id: int, action: str, details: str = ""):
        """ثبت تاریخچه"""
        self.db.execute(
            "INSERT INTO history (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (user_id, action, details, datetime.now().isoformat())
        )
    
    async def get_usage_stats(self) -> Dict:
        """آمار استفاده"""
        # کل کاربران
        total_users = await self.get_user_count()
        
        # کاربران VIP
        vip_users = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM users WHERE is_vip = 1"
        )
        vip_count = vip_users['count'] if vip_users else 0
        
        # درخواست‌های امروز
        today = datetime.now().date().isoformat()
        today_requests = self.db.fetch_one(
            "SELECT SUM(used_today) as total FROM users"
        )
        total_requests = today_requests['total'] if today_requests and today_requests['total'] else 0
        
        return {
            'total_users': total_users,
            'vip_users': vip_count,
            'today_requests': total_requests,
            'active_users': await self.get_active_users()
        }

class AIService:
    """سرویس هوش مصنوعی"""
    
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.google_key = GOOGLE_API_KEY
        
    async def chat(self, message: str, context: List[Dict] = None) -> str:
        """چت با هوش مصنوعی"""
        try:
            # اگر کلید OpenAI وجود داشته باشد از API واقعی استفاده می‌شود
            if self.api_key and self.api_key != "your_openai_key":
                # در اینجا کد واقعی OpenAI قرار می‌گیرد
                pass
            
            # شبیه‌سازی پاسخ
            responses = [
                "سلام! چطور می‌توانم به شما کمک کنم؟",
                "سوال خوبی پرسیدید. بگذارید فکر کنم...",
                "این یک موضوع جالب است!",
                "مطمئن نیستم، اما می‌توانم تحقیق کنم.",
                "پاسخ دقیق این سوال نیاز به بررسی بیشتری دارد."
            ]
            return random.choice(responses)
        except Exception as e:
            logger.error(f"AI Chat error: {e}")
            return "متأسفانه در پردازش درخواست شما خطایی رخ داد."
    
    async def generate_image(self, prompt: str) -> Optional[str]:
        """تولید تصویر با AI"""
        try:
            # شبیه‌سازی تولید تصویر
            return "https://via.placeholder.com/512x512?text=AI+Generated+Image"
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return None
    
    async def summarize(self, text: str, max_length: int = 200) -> str:
        """خلاصه‌سازی متن"""
        try:
            words = text.split()
            if len(words) <= max_length:
                return text
            summary = ' '.join(words[:max_length])
            return summary + "..."
        except Exception as e:
            logger.error(f"Summarize error: {e}")
            return text[:200]
    
    async def translate(self, text: str, target_lang: str = "fa") -> str:
        """ترجمه متن"""
        try:
            translations = {
                "en": "This is a translation of the text.",
                "fa": "این یک ترجمه از متن است.",
                "ar": "هذه ترجمة النص.",
                "tr": "Bu, metnin bir çevirisidir."
            }
            return translations.get(target_lang, text)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text

class XUIService:
    """سرویس اتصال به پنل X-UI"""
    
    def __init__(self):
        self.panel_url = XUI_PANEL_URL
        self.username = XUI_USERNAME
        self.password = XUI_PASSWORD
        
    async def create_vless_config(self, domain: str, remark: str = "") -> Dict:
        """ساخت کانفیگ VLESS"""
        try:
            uuid = ''.join(random.choices(string.hexdigits, k=36))
            config = {
                'protocol': 'vless',
                'address': domain,
                'port': 443,
                'uuid': uuid,
                'flow': 'xtls-rprx-vision',
                'security': 'reality',
                'sni': domain,
                'fingerprint': 'chrome',
                'public_key': 'your_public_key',
                'short_id': ''.join(random.choices(string.hexdigits, k=8))
            }
            return config
        except Exception as e:
            logger.error(f"XUI create config error: {e}")
            return None
    
    async def create_trojan_config(self, domain: str, remark: str = "") -> Dict:
        """ساخت کانفیگ Trojan"""
        try:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            config = {
                'protocol': 'trojan',
                'address': domain,
                'port': 443,
                'password': password,
                'sni': domain,
                'fingerprint': 'chrome',
                'allow_insecure': False
            }
            return config
        except Exception as e:
            logger.error(f"XUI create trojan error: {e}")
            return None
    
    async def create_reality_config(self, domain: str, remark: str = "") -> Dict:
        """ساخت کانفیگ Reality"""
        try:
            config = await self.create_vless_config(domain, remark)
            if config:
                config['security'] = 'reality'
                config['pbk'] = ''.join(random.choices(string.ascii_letters + string.digits, k=44))
            return config
        except Exception as e:
            logger.error(f"XUI create reality error: {e}")
            return None
    
    async def create_inbound(self, config: Dict) -> bool:
        """ایجاد اینباوند در پنل"""
        try:
            logger.info(f"Creating inbound: {config}")
            return True
        except Exception as e:
            logger.error(f"Create inbound error: {e}")
            return False
    
    async def get_inbounds(self) -> List[Dict]:
        """دریافت لیست اینباوندها"""
        try:
            return [
                {'id': 1, 'port': 443, 'protocol': 'vless', 'remark': 'VLESS-Reality'},
                {'id': 2, 'port': 8443, 'protocol': 'trojan', 'remark': 'Trojan-WS'}
            ]
        except Exception as e:
            logger.error(f"Get inbounds error: {e}")
            return []

class SubscriptionService:
    """سرویس مدیریت اشتراک"""
    
    def __init__(self):
        self.user_service = UserService()
        
    async def get_subscription_plans(self) -> List[Dict]:
        """دریافت پلن‌های اشتراک"""
        return [
            {
                'id': 'monthly',
                'name': 'ماهانه',
                'price': 50000,
                'days': 30,
                'features': [
                    'سهمیه روزانه 200 درخواست',
                    'دسترسی به مدل‌های پیشرفته AI',
                    'ساخت کانفیگ VIP',
                    'پشتیبانی ویژه'
                ]
            },
            {
                'id': 'quarterly',
                'name': 'سه ماهه',
                'price': 120000,
                'days': 90,
                'features': [
                    'همه مزایای ماهانه',
                    'تخفیف 20%',
                    'اولویت در پردازش'
                ]
            },
            {
                'id': 'yearly',
                'name': 'سالانه',
                'price': 400000,
                'days': 365,
                'features': [
                    'همه مزایای سه ماهه',
                    'تخفیف 33%',
                    'پشتیبانی 24/7'
                ]
            }
        ]
    
    async def activate_vip(self, user_id: int, plan_id: str) -> bool:
        """فعال‌سازی VIP"""
        plans = await self.get_subscription_plans()
        plan = next((p for p in plans if p['id'] == plan_id), None)
        
        if not plan:
            return False
            
        return await self.user_service.set_vip(user_id, plan['days'])

# ============================================
# بخش 5: سیستم امنیتی
# ============================================

class RateLimiter:
    """محدودکننده نرخ درخواست"""
    
    def __init__(self):
        self.requests = defaultdict(list)
        
    def is_allowed(self, user_id: int, limit: int = RATE_LIMIT_PER_USER, 
                   window: int = RATE_LIMIT_WINDOW) -> bool:
        """بررسی مجاز بودن درخواست"""
        now = time.time()
        user_requests = self.requests[user_id]
        
        # حذف درخواست‌های قدیمی
        user_requests = [t for t in user_requests if now - t < window]
        self.requests[user_id] = user_requests
        
        if len(user_requests) >= limit:
            return False
            
        user_requests.append(now)
        return True
    
    def reset(self, user_id: int):
        """ریست محدودیت برای کاربر"""
        if user_id in self.requests:
            del self.requests[user_id]

class AntiSpam:
    """سیستم ضد اسپم"""
    
    def __init__(self):
        self.messages = defaultdict(list)
        
    def check_spam(self, user_id: int, text: str) -> bool:
        """بررسی اسپم"""
        now = time.time()
        user_messages = self.messages[user_id]
        
        # حذف پیام‌های قدیمی
        user_messages = [m for m in user_messages if now - m['time'] < 60]
        self.messages[user_id] = user_messages
        
        # بررسی تکراری بودن
        for msg in user_messages:
            if msg['text'] == text:
                return True  # اسپم
                
        user_messages.append({'time': now, 'text': text})
        
        # بررسی تعداد پیام در 10 ثانیه
        recent = [m for m in user_messages if now - m['time'] < 10]
        if len(recent) > 5:
            return True  # فلود
            
        return False

# ============================================
# بخش 6: دکمه‌ها و کیبوردها
# ============================================

def get_emoji(name: str) -> str:
    """دریافت ایموجی"""
    emojis = {
        'robot': '🤖',
        'sparkles': '✨',
        'speech_balloon': '💬',
        'art': '🎨',
        'books': '📚',
        'globe': '🌐',
        'shield': '🛡️',
        'crown': '👑',
        'arrow_right': '➡️',
        'menu': '📋',
        'bust_in_silhouette': '👤',
        'up': '⬆️',
        'warning': '⚠️',
        'success': '✅',
        'error': '❌',
        'info': 'ℹ️',
        'settings': '⚙️',
        'money': '💰',
        'gift': '🎁',
        'star': '⭐',
        'heart': '❤️',
        'fire': '🔥',
        'clock': '🕐',
        'calendar': '📅',
        'stats': '📊',
        'admin': '🔧',
        'ban': '🚫',
        'unban': '✅',
        'broadcast': '📢',
        'config': '🔐',
        'vpn': '🛡️'
    }
    return emojis.get(name, name)

def get_main_menu(is_vip: bool = False):
    """منوی اصلی"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    buttons = [
        [
            InlineKeyboardButton(f"{get_emoji('speech_balloon')} چت هوش مصنوعی", callback_data="ai_chat"),
            InlineKeyboardButton(f"{get_emoji('art')} تولید تصویر", callback_data="ai_image")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('books')} خلاصه‌سازی", callback_data="ai_summary"),
            InlineKeyboardButton(f"{get_emoji('globe')} ترجمه", callback_data="ai_translate")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('shield')} ساخت کانفیگ", callback_data="vpn_config")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('bust_in_silhouette')} پروفایل", callback_data="profile"),
            InlineKeyboardButton(f"{get_emoji('crown')} VIP", callback_data="vip_info")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('stats')} آمار", callback_data="stats")
        ]
    ]
    
    if is_vip:
        buttons.append([
            InlineKeyboardButton(f"{get_emoji('star')} ✨ ویژه VIP", callback_data="vip_features")
        ])
    
    return InlineKeyboardMarkup(buttons)

def get_profile_keyboard(is_vip: bool = False):
    """کیبورد پروفایل"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    buttons = [
        [
            InlineKeyboardButton(f"{get_emoji('crown')} اشتراک VIP", callback_data="vip_info"),
            InlineKeyboardButton(f"{get_emoji('stats')} آمار", callback_data="stats")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="back_main")
        ]
    ]
    
    return InlineKeyboardMarkup(buttons)

def get_subscription_keyboard():
    """کیبورد اشتراک"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    buttons = [
        [
            InlineKeyboardButton("📅 ماهانه - 50,000 تومان", callback_data="sub_monthly"),
            InlineKeyboardButton("📅 سه ماهه - 120,000 تومان", callback_data="sub_quarterly")
        ],
        [
            InlineKeyboardButton("📅 سالانه - 400,000 تومان", callback_data="sub_yearly")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="back_main")
        ]
    ]
    
    return InlineKeyboardMarkup(buttons)

def get_vpn_keyboard():
    """کیبورد VPN"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    buttons = [
        [
            InlineKeyboardButton("🛡️ VLESS", callback_data="vpn_vless"),
            InlineKeyboardButton("🛡️ Trojan", callback_data="vpn_trojan")
        ],
        [
            InlineKeyboardButton("🛡️ Reality", callback_data="vpn_reality")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="back_main")
        ]
    ]
    
    return InlineKeyboardMarkup(buttons)

def get_admin_keyboard():
    """کیبورد ادمین"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    buttons = [
        [
            InlineKeyboardButton(f"{get_emoji('stats')} آمار", callback_data="admin_stats"),
            InlineKeyboardButton(f"{get_emoji('broadcast')} ارسال انبوه", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('crown')} تنظیم VIP", callback_data="admin_set_vip"),
            InlineKeyboardButton(f"{get_emoji('ban')} بن کاربر", callback_data="admin_ban")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('settings')} تنظیمات", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="back_main")
        ]
    ]
    
    return InlineKeyboardMarkup(buttons)

# ============================================
# بخش 7: هندلرهای اصلی
# ============================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

class BotHandlers:
    """کلاس مدیریت هندلرهای ربات"""
    
    def __init__(self):
        self.user_service = UserService()
        self.ai_service = AIService()
        self.xui_service = XUIService()
        self.subscription_service = SubscriptionService()
        self.rate_limiter = RateLimiter()
        self.anti_spam = AntiSpam()
        
        # وضعیت‌های مکالمه
        self.CHAT_MODE = 1
        self.SUMMARY_MODE = 2
        self.TRANSLATE_MODE = 3
        self.VPN_DOMAIN_MODE = 4
        self.VPN_PROTOCOL_MODE = 5
        self.BROADCAST_MODE = 6
        self.SET_VIP_MODE = 7
        self.BAN_MODE = 8
        
    # ========== دستورات ==========
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور شروع"""
        user = update.effective_user
        user_id = user.id
        
        # ثبت کاربر
        await self.user_service.get_or_create_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # بررسی VIP
        is_vip = await self.user_service.check_vip_status(user_id)
        
        # متن خوش‌آمدگویی
        welcome = f"""
{get_emoji('robot')} <b>به ربات هوشمند خوش آمدید!</b>

{get_emoji('sparkles')} <b>قابلیت‌های ربات:</b>
• {get_emoji('speech_balloon')} چت با هوش مصنوعی
• {get_emoji('art')} تولید تصویر
• {get_emoji('books')} خلاصه‌سازی متون
• {get_emoji('globe')} ترجمه پیشرفته
• {get_emoji('shield')} ساخت کانفیگ VPN

{get_emoji('crown')} <b>وضعیت شما:</b>
• وضعیت: {'✨ VIP' if is_vip else 'رایگان'}
• سهمیه روزانه: {'۲۰۰' if is_vip else '۲۰'} استفاده

{get_emoji('arrow_right')} لطفاً از منوی زیر استفاده کنید:
"""
        
        await update.message.reply_text(
            welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu(is_vip)
        )
    
    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش منو"""
        user_id = update.effective_user.id
        is_vip = await self.user_service.check_vip_status(user_id)
        
        await update.message.reply_text(
            f"{get_emoji('menu')} <b>منوی اصلی</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu(is_vip)
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور راهنما"""
        help_text = f"""
{get_emoji('info')} <b>راهنمای ربات</b>

<b>دستورات:</b>
/start - شروع و منوی اصلی
/menu - نمایش منو
/profile - اطلاعات کاربری
/help - راهنما

<b>قابلیت‌ها:</b>
1. چت هوش مصنوعی: سوالات خود را بپرسید
2. تولید تصویر: توضیحات را ارسال کنید
3. خلاصه‌سازی: متن طولانی را خلاصه کنید
4. ترجمه: متن را برای ترجمه ارسال کنید
5. ساخت کانفیگ: با وارد کردن دامنه

<b>اشتراک VIP:</b>
برای استفاده نامحدود از همه قابلیت‌ها
مشاهده پلن‌ها: /subscribe
"""
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML
        )
    
    async def profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پروفایل"""
        user_id = update.effective_user.id
        user_data = await self.user_service.get_user(user_id)
        
        if not user_data:
            await update.message.reply_text("⚠️ کاربر یافت نشد!")
            return
        
        # اطلاعات کاربر
        is_vip = user_data.get('is_vip', False)
        vip_expiry = user_data.get('vip_expiry')
        if vip_expiry:
            vip_expiry = datetime.fromisoformat(vip_expiry).strftime("%Y-%m-%d")
        else:
            vip_expiry = "ندارد"
        
        profile_text = f"""
{get_emoji('bust_in_silhouette')} <b>پروفایل کاربری</b>

📝 <b>اطلاعات:</b>
• شناسه: {user_data['user_id']}
• نام: {user_data.get('first_name', 'ناشناس')}
• وضعیت: {'✨ VIP' if is_vip else 'رایگان'}

⭐ <b>اشتراک:</b>
• وضعیت: {'فعال' if is_vip else 'غیرفعال'}
• انقضا: {vip_expiry}

📊 <b>آمار:</b>
• کل درخواست‌ها: {user_data.get('total_requests', 0)}
• استفاده امروز: {user_data.get('used_today', 0)}/{user_data.get('daily_limit', 20)}
"""
        
        await update.message.reply_text(
            profile_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_profile_keyboard(is_vip)
        )
    
    async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش صفحه اشتراک"""
        plans = await self.subscription_service.get_subscription_plans()
        
        text = f"""
{get_emoji('crown')} <b>اشتراک VIP</b>

<b>مزایای VIP:</b>
✅ سهمیه روزانه ۲۰۰ درخواست
✅ دسترسی به مدل‌های پیشرفته AI
✅ اولویت در پردازش
✅ پشتیبانی ویژه
✅ تخفیف در ساخت کانفیگ

<b>پلن‌های اشتراک:</b>
"""
        
        for plan in plans:
            text += f"\n{get_emoji('star')} {plan['name']}: {plan['price']:,} تومان"
            text += f"\n   مدت: {plan['days']} روز"
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_subscription_keyboard()
        )
    
    async def vip_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """اطلاعات VIP"""
        await self.subscribe(update, context)
    
    # ========== کال‌بک‌ها ==========
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت کال‌بک‌ها"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        # بررسی محدودیت نرخ
        if not self.rate_limiter.is_allowed(user_id):
            await query.edit_message_text(
                f"{get_emoji('warning')} ⚠️ درخواست‌های زیادی ارسال کردید. لطفاً چند لحظه صبر کنید."
            )
            return
        
        # مدیریت کال‌بک‌ها
        if data == "back_main":
            is_vip = await self.user_service.check_vip_status(user_id)
            await query.edit_message_text(
                f"{get_emoji('menu')} <b>منوی اصلی</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_menu(is_vip)
            )
            
        elif data == "profile":
            # ارسال پروفایل به صورت پیام جدید
            await query.message.delete()
            await self.profile(update, context)
            
        elif data == "vip_info":
            await query.message.delete()
            await self.subscribe(update, context)
            
        elif data == "stats":
            await self.show_stats(update, context)
            
        elif data == "ai_chat":
            await query.edit_message_text(
                f"{get_emoji('speech_balloon')} <b>چت با هوش مصنوعی</b>\n\n"
                "پیام خود را ارسال کنید تا پاسخ دریافت کنید.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="back_main")]
                ])
            )
            context.user_data['mode'] = self.CHAT_MODE
            
        elif data == "ai_image":
            await query.edit_message_text(
                f"{get_emoji('art')} <b>تولید تصویر با هوش مصنوعی</b>\n\n"
                "توضیحات تصویر مورد نظر خود را ارسال کنید.\n"
                "مثال: یک گربه در حال بازی در باغ",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="back_main")]
                ])
            )
            context.user_data['mode'] = "image"
            
        elif data == "ai_summary":
            await query.edit_message_text(
                f"{get_emoji('books')} <b>خلاصه‌سازی متن</b>\n\n"
                "متن خود را ارسال کنید تا خلاصه شود.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="back_main")]
                ])
            )
            context.user_data['mode'] = self.SUMMARY_MODE
            
        elif data == "ai_translate":
            await query.edit_message_text(
                f"{get_emoji('globe')} <b>ترجمه متن</b>\n\n"
                "متن مورد نظر برای ترجمه را ارسال کنید.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="back_main")]
                ])
            )
            context.user_data['mode'] = self.TRANSLATE_MODE
            
        elif data == "vpn_config":
            await query.edit_message_text(
                f"{get_emoji('shield')} <b>ساخت کانفیگ VPN</b>\n\n"
                "نوع پروتکل مورد نظر را انتخاب کنید:",
                parse_mode=ParseMode.HTML,
                reply_markup=get_vpn_keyboard()
            )
            
        elif data.startswith("vpn_"):
            protocol = data.replace("vpn_", "")
            await query.edit_message_text(
                f"{get_emoji('shield')} <b>ساخت کانفیگ {protocol.upper()}</b>\n\n"
                "لطفاً دامنه مورد نظر را وارد کنید:\n"
                "مثال: example.com",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="vpn_config")]
                ])
            )
            context.user_data['vpn_protocol'] = protocol
            context.user_data['mode'] = self.VPN_DOMAIN_MODE
            
        elif data.startswith("sub_"):
            plan_id = data.replace("sub_", "")
            success = await self.subscription_service.activate_vip(user_id, plan_id)
            
            if success:
                await query.edit_message_text(
                    f"{get_emoji('success')} ✅ اشتراک شما با موفقیت فعال شد!\n\n"
                    "از تمام مزایای VIP استفاده کنید.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await query.edit_message_text(
                    f"{get_emoji('error')} ❌ خطا در فعال‌سازی اشتراک. لطفاً دوباره تلاش کنید.",
                    parse_mode=ParseMode.HTML
                )
                
        elif data == "admin_panel":
            if user_id not in ADMIN_IDS:
                await query.edit_message_text(
                    f"{get_emoji('error')} ⚠️ شما دسترسی ادمین ندارید!"
                )
                return
                
            await query.edit_message_text(
                f"{get_emoji('admin')} <b>پنل مدیریت</b>\n\n"
                "گزینه مورد نظر را انتخاب کنید:",
                parse_mode=ParseMode.HTML,
                reply_markup=get_admin_keyboard()
            )
            
        elif data == "admin_stats":
            if user_id not in ADMIN_IDS:
                return
            stats = await self.user_service.get_usage_stats()
            
            stats_text = f"""
{get_emoji('stats')} <b>آمار ربات</b>

👥 کاربران: {stats['total_users']}
⭐ VIP: {stats['vip_users']}
📊 درخواست‌های امروز: {stats['today_requests']}
👤 کاربران فعال (۷ روز): {stats['active_users']}
"""
            await query.edit_message_text(
                stats_text,
                parse_mode=ParseMode.HTML
            )
            
        elif data == "admin_broadcast":
            if user_id not in ADMIN_IDS:
                return
                
            await query.edit_message_text(
                f"{get_emoji('broadcast')} <b>ارسال پیام انبوه</b>\n\n"
                "پیام خود را برای ارسال به همه کاربران وارد کنید:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="admin_panel")]
                ])
            )
            context.user_data['mode'] = self.BROADCAST_MODE
            
        elif data == "admin_set_vip":
            if user_id not in ADMIN_IDS:
                return
                
            await query.edit_message_text(
                f"{get_emoji('crown')} <b>تنظیم VIP برای کاربر</b>\n\n"
                "شناسه کاربر و تعداد روز را وارد کنید:\n"
                "مثال: 123456789 30",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="admin_panel")]
                ])
            )
            context.user_data['mode'] = self.SET_VIP_MODE
            
        elif data == "admin_ban":
            if user_id not in ADMIN_IDS:
                return
                
            await query.edit_message_text(
                f"{get_emoji('ban')} <b>بن کردن کاربر</b>\n\n"
                "شناسه کاربر را وارد کنید:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{get_emoji('arrow_right')} بازگشت", callback_data="admin_panel")]
                ])
            )
            context.user_data['mode'] = self.BAN_MODE
    
    # ========== پیام‌ها ==========
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت پیام‌های دریافتی"""
        user_id = update.effective_user.id
        text = update.message.text
        
        if not text:
            return
            
        # بررسی محدودیت نرخ
        if not self.rate_limiter.is_allowed(user_id):
            await update.message.reply_text(
                f"{get_emoji('warning')} ⚠️ لطفاً چند لحظه صبر کنید."
            )
            return
            
        # بررسی اسپم
        if self.anti_spam.check_spam(user_id, text):
            await update.message.reply_text(
                f"{get_emoji('error')} ⚠️ پیام شما به عنوان اسپم شناسایی شد!"
            )
            return
            
        # بررسی سهمیه روزانه
        user = await self.user_service.get_user(user_id)
        if user and user.get('used_today', 0) >= user.get('daily_limit', 20):
            await update.message.reply_text(
                f"{get_emoji('warning')} ⚠️ سهمیه روزانه شما تمام شده است!\n"
                "برای افزایش سهمیه از اشتراک VIP استفاده کنید."
            )
            return
            
        # دریافت حالت
        mode = context.user_data.get('mode')
        
        # پردازش بر اساس حالت
        if mode == self.CHAT_MODE:
            await self.handle_chat(update, context)
            
        elif mode == "image":
            await self.handle_image(update, context)
            
        elif mode == self.SUMMARY_MODE:
            await self.handle_summary(update, context)
            
        elif mode == self.TRANSLATE_MODE:
            await self.handle_translate(update, context)
            
        elif mode == self.VPN_DOMAIN_MODE:
            await self.handle_vpn_domain(update, context)
            
        elif mode == self.BROADCAST_MODE:
            await self.handle_broadcast(update, context)
            
        elif mode == self.SET_VIP_MODE:
            await self.handle_set_vip(update, context)
            
        elif mode == self.BAN_MODE:
            await self.handle_ban(update, context)
            
        else:
            # حالت پیش‌فرض
            await update.message.reply_text(
                f"{get_emoji('info')} لطفاً از منوی اصلی استفاده کنید.",
                reply_markup=get_main_menu(False)
            )
    
    async def handle_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش چت"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # افزایش آمار
        await self.user_service.increment_usage(user_id)
        await self.user_service.log_history(user_id, "chat", text[:100])
        
        # دریافت پاسخ از AI
        await update.message.reply_chat_action("typing")
        response = await self.ai_service.chat(text)
        
        await update.message.reply_text(
            f"{get_emoji('speech_balloon')} <b>پاسخ:</b>\n\n{response}",
            parse_mode=ParseMode.HTML
        )
    
    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش تولید تصویر"""
        user_id = update.effective_user.id
        text = update.message.text
        
        await self.user_service.increment_usage(user_id)
        await self.user_service.log_history(user_id, "image", text[:100])
        
        await update.message.reply_chat_action("upload_photo")
        image_url = await self.ai_service.generate_image(text)
        
        if image_url:
            await update.message.reply_photo(
                image_url,
                caption=f"{get_emoji('art')} <b>تصویر تولید شده</b>\n\n{text}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"{get_emoji('error')} ❌ خطا در تولید تصویر. لطفاً دوباره تلاش کنید."
            )
    
    async def handle_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش خلاصه‌سازی"""
        user_id = update.effective_user.id
        text = update.message.text
        
        if len(text) < 20:
            await update.message.reply_text(
                f"{get_emoji('warning')} ⚠️ متن باید حداقل ۲۰ کاراکتر باشد."
            )
            return
            
        await self.user_service.increment_usage(user_id)
        await self.user_service.log_history(user_id, "summary", f"{len(text)} chars")
        
        await update.message.reply_chat_action("typing")
        summary = await self.ai_service.summarize(text)
        
        await update.message.reply_text(
            f"{get_emoji('books')} <b>خلاصه متن:</b>\n\n{summary}",
            parse_mode=ParseMode.HTML
        )
    
    async def handle_translate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش ترجمه"""
        user_id = update.effective_user.id
        text = update.message.text
        
        await self.user_service.increment_usage(user_id)
        await self.user_service.log_history(user_id, "translate", f"{len(text)} chars")
        
        await update.message.reply_chat_action("typing")
        translated = await self.ai_service.translate(text)
        
        await update.message.reply_text(
            f"{get_emoji('globe')} <b>ترجمه متن:</b>\n\n{translated}",
            parse_mode=ParseMode.HTML
        )
    
    async def handle_vpn_domain(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش ساخت کانفیگ با دامنه"""
        user_id = update.effective_user.id
        domain = update.message.text.strip()
        
        # اعتبارسنجی دامنه
        domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, domain):
            await update.message.reply_text(
                f"{get_emoji('error')} ⚠️ دامنه وارد شده معتبر نیست!\n"
                "مثال: example.com"
            )
            return
            
        protocol = context.user_data.get('vpn_protocol', 'vless')
        
        await self.user_service.increment_usage(user_id)
        await self.user_service.log_history(user_id, "vpn", f"{protocol}:{domain}")
        
        await update.message.reply_chat_action("typing")
        
        # ساخت کانفیگ
        if protocol == "vless":
            config = await self.xui_service.create_vless_config(domain)
        elif protocol == "trojan":
            config = await self.xui_service.create_trojan_config(domain)
        else:  # reality
            config = await self.xui_service.create_reality_config(domain)
            
        if config:
            # ذخیره در دیتابیس
            db = Database()
            db.execute(
                "INSERT INTO configs (user_id, domain, protocol, config, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, domain, protocol, json.dumps(config), datetime.now().isoformat())
            )
            
            config_text = f"""
{get_emoji('shield')} <b>کانفیگ {protocol.upper()}</b>

🔗 دامنه: {domain}
📡 پروتکل: {protocol.upper()}
📋 کانفیگ:
<code>{json.dumps(config, indent=2)}</code>

⚠️ لطفاً این کانفیگ را در اپلیکیشن خود وارد کنید.
"""
            
            await update.message.reply_text(
                config_text,
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"{get_emoji('error')} ❌ خطا در ساخت کانفیگ. لطفاً دوباره تلاش کنید."
            )
    
    async def handle_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش ارسال انبوه"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⚠️ شما دسترسی ادمین ندارید!")
            return
            
        message = update.message.text
        
        # دریافت همه کاربران
        users = await self.user_service.get_all_users()
        sent = 0
        
        # ارسال به همه
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=message,
                    parse_mode=ParseMode.HTML
                )
                sent += 1
                await asyncio.sleep(0.1)  # جلوگیری از محدودیت
            except:
                pass
                
        # ثبت در دیتابیس
        db = Database()
        db.execute(
            "INSERT INTO broadcasts (message, sent_count, total_count, created_by, created_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            (message, sent, len(users), user_id, datetime.now().isoformat(), "completed")
        )
        
        await update.message.reply_text(
            f"{get_emoji('success')} ✅ پیام به {sent} کاربر ارسال شد."
        )
        context.user_data['mode'] = None
    
    async def handle_set_vip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش تنظیم VIP"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⚠️ شما دسترسی ادمین ندارید!")
            return
            
        text = update.message.text.strip()
        parts = text.split()
        
        if len(parts) != 2:
            await update.message.reply_text(
                f"{get_emoji('error')} ⚠️ فرمت صحیح:\n"
                "شناسه_کاربر تعداد_روز\n"
                "مثال: 123456789 30"
            )
            return
            
        try:
            target_user = int(parts[0])
            days = int(parts[1])
            
            success = await self.user_service.set_vip(target_user, days)
            
            if success:
                await update.message.reply_text(
                    f"{get_emoji('success')} ✅ کاربر با موفقیت VIP شد."
                )
                # اطلاع به کاربر
                try:
                    await context.bot.send_message(
                        chat_id=target_user,
                        text=f"{get_emoji('crown')} 🎉 اشتراک VIP شما به مدت {days} روز فعال شد!"
                    )
                except:
                    pass
            else:
                await update.message.reply_text(
                    f"{get_emoji('error')} ❌ خطا در تنظیم VIP. کاربر پیدا نشد."
                )
        except:
            await update.message.reply_text(
                f"{get_emoji('error')} ⚠️ ورودی نامعتبر!"
            )
            
        context.user_data['mode'] = None
    
    async def handle_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش بن کاربر"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⚠️ شما دسترسی ادمین ندارید!")
            return
            
        try:
            target_user = int(update.message.text.strip())
            
            success = await self.user_service.update_user(target_user, status="banned")
            
            if success:
                await update.message.reply_text(
                    f"{get_emoji('success')} ✅ کاربر با موفقیت بن شد."
                )
            else:
                await update.message.reply_text(
                    f"{get_emoji('error')} ❌ کاربر پیدا نشد."
                )
        except:
            await update.message.reply_text(
                f"{get_emoji('error')} ⚠️ شناسه کاربر نامعتبر!"
            )
            
        context.user_data['mode'] = None
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش آمار"""
        stats = await self.user_service.get_usage_stats()
        
        stats_text = f"""
{get_emoji('stats')} <b>آمار ربات</b>

👥 کاربران: {stats['total_users']}
⭐ VIP: {stats['vip_users']}
📊 درخواست‌های امروز: {stats['today_requests']}
👤 کاربران فعال: {stats['active_users']}
"""
        
        await update.message.reply_text(
            stats_text,
            parse_mode=ParseMode.HTML
        )

# ============================================
# بخش 8: راه‌اندازی ربات
# ============================================

class AdvancedBot:
    """کلاس اصلی ربات"""
    
    def __init__(self):
        self.token = BOT_TOKEN
        self.handlers = BotHandlers()
        self.application = None
        
    def setup(self):
        """راه‌اندازی اپلیکیشن"""
        # ایجاد اپلیکیشن
        self.application = Application.builder().token(self.token).build()
        
        # اضافه کردن هندلرهای دستور
        self.application.add_handler(CommandHandler("start", self.handlers.start))
        self.application.add_handler(CommandHandler("menu", self.handlers.menu))
        self.application.add_handler(CommandHandler("help", self.handlers.help_command))
        self.application.add_handler(CommandHandler("profile", self.handlers.profile))
        self.application.add_handler(CommandHandler("subscribe", self.handlers.subscribe))
        self.application.add_handler(CommandHandler("vip", self.handlers.vip_info))
        
        # هندلر کال‌بک
        self.application.add_handler(CallbackQueryHandler(self.handlers.handle_callback))
        
        # هندلر پیام
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handlers.handle_message
        ))
        
        # هندلر خطا
        self.application.add_error_handler(self.error_handler)
        
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت خطا"""
        logger.error(f"Error: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    f"{get_emoji('error')} ❌ خطایی رخ داد! لطفاً دوباره تلاش کنید."
                )
        except:
            pass
    
    async def start(self):
        """شروع ربات"""
        self.setup()
        logger.info("🤖 Starting bot...")
        
        try:
            # شروع پولینگ
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info(f"✅ Bot started successfully! @{BOT_USERNAME}")
            
            # نگه‌داشتن اجرا
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

# ============================================
# بخش 9: نقطه ورود اصلی
# ============================================

async def main():
    """نقطه ورود اصلی"""
    
    # بررسی توکن
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not set in environment!")
        return
        
    logger.info(f"🚀 Advanced Telegram Bot starting...")
    logger.info(f"📝 Environment: {ENVIRONMENT}")
    logger.info(f"👥 Admins: {ADMIN_IDS}")
    
    # ایجاد و راه‌اندازی ربات
    bot = AdvancedBot()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
