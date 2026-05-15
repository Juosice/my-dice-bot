import sqlite3
import os

DB_PATH = 'dice_game.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        coins INTEGER DEFAULT 1000
    )
    ''')
    
    # Bets table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        round_id INTEGER,
        bet_type TEXT,
        amount INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Game history table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        round_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dice1 INTEGER,
        dice2 INTEGER,
        total INTEGER,
        result_type TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id, username=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user and username:
        cursor.execute('INSERT INTO users (user_id, username, coins) VALUES (?, ?, ?)', (user_id, username, 1000))
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
    
    conn.close()
    return user

def update_coins(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def set_coins(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins = ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_top_users(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT username, coins FROM users ORDER BY coins DESC LIMIT ?', (limit,))
    top = cursor.fetchall()
    conn.close()
    return top

def place_bet(user_id, round_id, bet_type, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO bets (user_id, round_id, bet_type, amount) VALUES (?, ?, ?, ?)', 
                   (user_id, round_id, bet_type, amount))
    conn.commit()
    conn.close()

def get_round_bets(round_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, bet_type, amount FROM bets WHERE round_id = ?', (round_id,))
    bets = cursor.fetchall()
    conn.close()
    return bets

def save_history(dice1, dice2, total, result_type):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO history (dice1, dice2, total, result_type) VALUES (?, ?, ?, ?)', 
                   (dice1, dice2, total, result_type))
    round_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return round_id

def get_last_results(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dice1, dice2, total, result_type FROM history ORDER BY round_id DESC LIMIT ?', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def get_user_history(user_id, limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # This is a bit complex as we need to join bets with history
    cursor.execute('''
        SELECT h.dice1, h.dice2, h.total, h.result_type, b.bet_type, b.amount 
        FROM bets b 
        JOIN history h ON b.round_id = h.round_id 
        WHERE b.user_id = ? 
        ORDER BY h.round_id DESC LIMIT ?
    ''', (user_id, limit))
    history = cursor.fetchall()
    conn.close()
    return history

def get_user_by_username(username):
    if username.startswith('@'):
        username = username[1:]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None
