import logging
import random
import asyncio
import os
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from database import init_db, get_user, update_coins, set_coins, get_top_users, place_bet, get_round_bets, save_history, get_last_results, get_user_history, get_user_by_username

# Configuration
TOKEN = '8874103041:AAFqaqe8Ci4yzEB_uNuD-_Spi8nT4OBULj8'
ADMIN_ID = 6850662138
MIN_BET = 50
MAX_BET = 5000

# Game State
current_round_id = 0
is_round_active = False
round_bets = {} # {user_id: [{'type': 'B', 'amount': 100}, ...]}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or user.first_name)
    await update.message.reply_text(f"Welcome {user.first_name}! Roll Dice Bot မှ ကြိုဆိုပါတယ်။\n/rules ကိုနှိပ်ပြီး စည်းမျဉ်းများဖတ်ရှုနိုင်ပါတယ်။")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or user.first_name)
    await update.message.reply_text(f"💰 လက်ကျန် Coin: {db_user[2]} coins")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = get_top_users(10)
    text = "🏆 **Leaderboard (Top 10)**\n\n"
    for i, (username, coins) in enumerate(top_users, 1):
        text += f"{i}. {username} - {coins} coins\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📜 **ဂိမ်းစည်းမျဉ်းများ**\n\n"
        "Bet ပမာဏ: Min 50 - Max 5000\n"
        "အန်စာတုံး ၂ လုံးလှိမ့်မည်။\n\n"
        "🔹 **Small (S)**: ၂ မှ ၆ ထိ (2x ရမည်)\n"
        "🔹 **Lucky 7 (L)**: ၇ (4x ရမည်)\n"
        "🔹 **Big (B)**: ၈ မှ ၁၂ ထိ (2x ရမည်)\n\n"
        "**ဆော့ကစားပုံ:**\n"
        "Chat ထဲတွင် 'B 100' သို့မဟုတ် 'S 50' စသဖြင့် ရိုက်ထည့်ပါ။\n"
        "တစ်လှည့်တည်းမှာ B, S, L ကြိုက်သလို တွဲထိုးနိုင်ပါသည်။"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_hist = get_user_history(user.id, 10)
    if not user_hist:
        await update.message.reply_text("မှတ်တမ်းမရှိသေးပါ။")
        return
    
    text = "📜 **သင်၏ နောက်ဆုံး ၁၀ ပွဲရလဒ်**\n\n"
    for h in user_hist:
        # h: (dice1, dice2, total, result_type, bet_type, amount)
        win_status = "✅ Win" if h[3][0] == h[4] else "❌ Lose"
        text += f"🎲 {h[0]}+{h[1]}={h[2]} ({h[3]}) | Bet: {h[4]} {h[5]} | {win_status}\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_res = get_last_results(10)
    if not last_res:
        await update.message.reply_text("မှတ်တမ်းမရှိသေးပါ။")
        return
    
    text = "📊 **နောက်ဆုံး ၁၀ ပွဲ ရလဒ်များ**\n\n"
    for r in last_res:
        # r: (dice1, dice2, total, result_type)
        text += f"🎲 {r[0]}+{r[1]}={r[2]} -> **{r[3]}**\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def handle_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_round_active, round_bets
    if not is_round_active:
        return # Don't reply if no round is active to avoid spam

    text = update.message.text.upper().split()
    if len(text) != 2:
        return

    bet_type = text[0]
    try:
        amount = int(text[1])
    except ValueError:
        return

    if bet_type not in ['B', 'S', 'L']:
        return

    if amount < MIN_BET or amount > MAX_BET:
        await update.message.reply_text(f"❌ Bet ပမာဏသည် {MIN_BET} နှင့် {MAX_BET} ကြား ဖြစ်ရပါမည်။")
        return

    user = update.effective_user
    db_user = get_user(user.id, user.username or user.first_name)
    
    # Check current pending bets for this user in this round
    pending_total = sum(b['amount'] for b in round_bets.get(user.id, []))
    
    if db_user[2] < (pending_total + amount):
        await update.message.reply_text("❌ လက်ကျန် Coin မလုံလောက်ပါ။")
        return

    # Record bet
    if user.id not in round_bets:
        round_bets[user.id] = []
    
    round_bets[user.id].append({'type': bet_type, 'amount': amount})
    await update.message.reply_text(f"✅ {bet_type} မှာ {amount} coins ထိုးလိုက်ပါပြီ။")

# Admin Commands
async def start_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_round_active, round_bets
    if update.effective_user.id != ADMIN_ID:
        return

    if is_round_active:
        await update.message.reply_text("Round တစ်ခု စတင်နေဆဲ ဖြစ်သည်။")
        return

    is_round_active = True
    round_bets = {}
    await update.message.reply_text("🎲 **Round စတင်ပါပြီ!**\n\nထိုးကြေးများကို ၃၅ စက္ကန့်အတွင်း ထည့်သွင်းနိုင်ပါသည်။\n(ဥပမာ - B 100, S 50, L 200)", parse_mode='Markdown')
    
    await asyncio.sleep(35)
    await finish_round(context)

async def finish_round(context: ContextTypes.DEFAULT_TYPE):
    global is_round_active, round_bets
    is_round_active = False
    
    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    
    res_type = ""
    if 2 <= total <= 6: res_type = "Small"
    elif total == 7: res_type = "Lucky 7"
    else: res_type = "Big"
    
    round_id = save_history(d1, d2, total, res_type)
    
    summary = f"🎲 **ရလဒ်ထွက်ပါပြီ!**\n\nအန်စာတုံး: {d1} + {d2} = **{total}**\nရလဒ်: **{res_type}**\n\n"
    
    winners_text = "🏆 **Winners:**\n"
    has_winners = False

    for user_id, bets in round_bets.items():
        total_win = 0
        total_lost = 0
        for b in bets:
            place_bet(user_id, round_id, b['type'], b['amount'])
            
            is_win = False
            multiplier = 0
            if b['type'] == 'S' and res_type == "Small":
                is_win, multiplier = True, 2
            elif b['type'] == 'L' and res_type == "Lucky 7":
                is_win, multiplier = True, 4
            elif b['type'] == 'B' and res_type == "Big":
                is_win, multiplier = True, 2
            
            if is_win:
                win_amt = b['amount'] * multiplier
                total_win += win_amt
            else:
                total_lost += b['amount']
        
        net_change = total_win - total_lost
        update_coins(user_id, net_change)
        
        if total_win > 0:
            has_winners = True
            user_info = await context.bot.get_chat(user_id)
            winners_text += f"👤 {user_info.first_name}: +{total_win} coins\n"

    if not has_winners:
        winners_text += "ယခုပွဲတွင် အနိုင်ရသူမရှိပါ။"
    
    # Log to file
    with open("game_log.txt", "a") as f:
        f.write(f"Round {round_id}: {d1}+{d2}={total} ({res_type})\n")

    await context.bot.send_message(chat_id=ADMIN_ID, text=summary + winners_text, parse_mode='Markdown')
    # Note: In a real group bot, you'd send this to the group chat ID. 
    # For now, sending to admin as requested.

async def add_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addcoin @username 1000")
        return
    
    username = context.args[0]
    amount = int(context.args[1])
    user_id = get_user_by_username(username)
    
    if user_id:
        update_coins(user_id, amount)
        await update.message.reply_text(f"✅ {username} ထံ {amount} coins ထည့်သွင်းပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ User ကို ရှာမတွေ့ပါ။")

async def remove_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removecoin @username 500")
        return
    
    username = context.args[0]
    amount = int(context.args[1])
    user_id = get_user_by_username(username)
    
    if user_id:
        update_coins(user_id, -amount)
        await update.message.reply_text(f"✅ {username} ထံမှ {amount} coins နှုတ်ယူပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ User ကို ရှာမတွေ့ပါ။")

async def set_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setcoin @username 5000")
        return
    
    username = context.args[0]
    amount = int(context.args[1])
    user_id = get_user_by_username(username)
    
    if user_id:
        set_coins(user_id, amount)
        await update.message.reply_text(f"✅ {username} ၏ Coin ကို {amount} သို့ သတ်မှတ်ပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ User ကို ရှာမတွေ့ပါ။")

async def reset_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /reset @username")
        return
    
    username = context.args[0]
    user_id = get_user_by_username(username)
    
    if user_id:
        set_coins(user_id, 0)
        await update.message.reply_text(f"✅ {username} ၏ Coin ကို 0 သို့ Reset လုပ်ပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ User ကို ရှာမတွေ့ပါ။")

if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Member Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('balance', balance))
    application.add_handler(CommandHandler('top', top))
    application.add_handler(CommandHandler('rules', rules))
    application.add_handler(CommandHandler('history', history))
    application.add_handler(CommandHandler('results', results))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_bet))
    
    # Admin Handlers
    application.add_handler(CommandHandler('start_round', start_round))
    application.add_handler(CommandHandler('addcoin', add_coin))
    application.add_handler(CommandHandler('removecoin', remove_coin))
    application.add_handler(CommandHandler('setcoin', set_coin))
    application.add_handler(CommandHandler('reset', reset_coin))
    
    print("Bot is running...")
    application.run_polling()
