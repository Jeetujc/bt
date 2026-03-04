import mysql.connector
from admin import load_config, get_cut_for_number
import requests
from decimal import Decimal

def send_summary_to_all_users(db):
    """
    Send betting summary to all users, including today's, old, weekly, etc.
    """
    try:
        cursor = db.cursor()
        cursor.execute("SELECT phone_no, total_bet, total_win, old_balance FROM users")
        user_data = cursor.fetchall()
        for phone_no, total_bet, total_win, old_balance in user_data:
            try:
                total_bet = float(total_bet) if total_bet else 0.0
                total_win = float(total_win) if total_win else 0.0
                old_balance = float(old_balance) if old_balance else 0.0

                commission = total_bet / 10
                base_amount = total_bet - total_win - commission
                user_cut_percentage = get_cut_for_number(phone_no)
                user_cut_amount = base_amount * user_cut_percentage
                net_total = base_amount - user_cut_amount

                # Today's bet/win
                # cursor.execute(
                #     "SELECT IFNULL(SUM(amount),0), IFNULL(SUM(win_amount),0) FROM bet_slips WHERE phone_no = %s AND DATE(created_at) = CURDATE()", 
                #     (phone_no,))
                # today_bet, today_win = cursor.fetchone()
                # today_bet = float(today_bet) if today_bet else 0.0
                # today_win = float(today_win) if today_win else 0.0
                # today_commission = today_bet / 10
                # today_base = today_bet - today_win - today_commission
                # today_cut = today_base * user_cut_percentage
                # today_net = today_base - today_cut

                message = f"""📊 *YOUR BETTING SUMMARY*

💰 Total Bet: ₹{total_bet:,.2f}
🏆 Total Win: ₹{total_win:,.2f}
💼 Commission: ₹{commission:,.2f}
✂️ Your Cut ({user_cut_percentage*100:.1f}%): ₹{user_cut_amount:,.2f}
📅 Todays: ₹{-1*net_total:,.2f}
Old: ₹{-1*old_balance:,.2f}
💵 Net Total: ₹{-1*(net_total + old_balance):,.2f}
"""
                cursor.execute("UPDATE users SET old_balance = %s WHERE phone_no = %s", (net_total+old_balance, phone_no))
                response = requests.post('http://localhost:3001/send-message', json={
                    'number': f"{phone_no}@c.us",
                    'message': message
                })
                requests.post('http://localhost:3001/send-message', json={
                    'number': f"{phone_no}@lid",
                    'message': message
                })
                if response.status_code == 200:
                    print(f"✅ Summary sent to {phone_no}")
                else:
                    print(f"❌ Failed to send to {phone_no}")
            except Exception as e:
                print(f"❌ Error sending to {phone_no}: {e}")
        cursor.close()
    except Exception as e:
        print(f"❌ Error in send_summary_to_all_users: {e}")

# WEEKLY OLD BALANCE UPDATE (ONLY SUNDAY)

def update_old_balance(db):
    """Update old_balance for all users (run only on Sunday after summary)"""
    try:
        cursor = db.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # Clear bet-related tables
        tables = ['users']
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            cursor.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")
    except Exception as e:
        print(f"❌ Error in update_old_balance: {e}")

# DAILY RESET (DO NOT TOUCH old_balance EXCEPT SUNDAY)

def reset_all(db):
    """
    Daily reset:
    - Clear bet_slips and bet_tracking tables
    - Reset total_bet and total_win in users
    - Preserve old_balance (only updated separately on Sundays)
    """
    try:
        cursor = db.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # Clear bet-related tables
        tables = ['bet_slips', 'bet_tracking']
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            cursor.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")
        
        # Reset user daily counters but keep old_balance untouched
        cursor.execute("UPDATE users SET total_bet = 0, total_win = 0")
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        db.commit()
        print("✅ Daily reset completed (old_balance preserved)")
        cursor.close()
        return True
    except Exception as e:
        if db:
            db.rollback()
        print(f"❌ Error in reset_all: {e}")
        return False

