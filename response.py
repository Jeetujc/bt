from placebet import placebet, get_next_event, events, get
import datetime as dt

def generate_reply(number, message, db, replied_msg=None):
    """
    Generate reply based on user message
    
    Args:
        number: User's WhatsApp number
        message: Current message content
        db: Database connection
        replied_msg: Content of replied message (if any)
    """
    try:
        message_lower = message.lower().strip()
        
        # ✅ Check for greetings first
        if is_greeting_message(message_lower):
            return generate_greeting_reply(number, db)
        
        # Check if it's a betting message
        elif is_betting_message(message):
            return placebet(number, message, db, replied_msg)
        
        # Handle other commands
        elif message_lower in ['balance', 'bal']:
            return get_balance(number, db)
        
        elif message_lower in ['help', 'commands']:
            return get_help_message()
        
        elif message_lower in ['status', 'events']:
            return get_events_status()
        
        # Add other command handlers here
        else:
            return "❓ Unknown command. Type 'help' for available commands."
            
    except Exception as e:
        print(f"❌ Error in generate_reply: {e}")
        return "❌ An error occurred. Please try again."

def get_balance(number, db):
    """Get user's balance information"""
    try:
        # Get user stats with proper error handling
        user_stats = get(number, db=db)
        if user_stats is None:
            return "❌ Unable to fetch your account details. Please contact support."
        
        total_bet, total_win = user_stats
        commission = total_bet / 10
        balance = total_win - total_bet+commission 
        # Get current bets by event with correct parameter order
        current_bets = {}
        for event_code in ['bd', 'kd', 'bn', 'kn']:
            try:
                open_total = get(number, event_code, 'open', db, True) or 0
                close_total = get(number, event_code, 'close', db, True) or 0
                
                if open_total > 0 or close_total > 0:
                    current_bets[event_code.upper()] = {
                        'open': open_total,
                        'close': close_total
                    }
            except Exception as e:
                print(f"❌ Error getting bets for {event_code}: {e}")
                continue
        
        # Format response
        balance_msg = (
            f"💰 **Your Balance Summary** 💰\n\n"
            f"💸 Total Bet: ₹{total_bet}\n"
            f"💵 Total Win: ₹{total_win}\n"
            f"🧾 Commission: ₹{commission}\n"#new
            f"🏦 Balance: ₹{balance}\n\n"
        )
        
        if current_bets:
            balance_msg += "📊 **Current Bets:**\n"
            for event, amounts in current_bets.items():
                if amounts['open'] > 0:
                    balance_msg += f"• {event} Open: ₹{amounts['open']}\n"
                if amounts['close'] > 0:
                    balance_msg += f"• {event} Close: ₹{amounts['close']}\n"
        else:
            balance_msg += "📊 No current bets placed."
        
        
        
        return balance_msg
        
    except Exception as e:
        print(f"❌ Error getting balance: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return "❌ Unable to fetch balance. Please try again."

def is_greeting_message(message_lower):
    """Check if message is a greeting"""
    greetings = [
        'hi', 'hello', 'hey', 'hii', 'hiii', 'heyyy',
        'good morning', 'good afternoon', 'good evening', 'good night',
        'gm', 'ga', 'ge', 'gn',
        'namaste', 'namaskar',
        'sat sri akal', 'adab', 'salaam', 'salam',
        'howdy', 'yo', 'sup', 'wassup', 'whatsup',
        'greetings', 'salutations'
    ]
    
    return message_lower in greetings

def generate_greeting_reply(number, db):
    """Generate personalized greeting reply with current info"""
    try:
        # Get current time info
        now = dt.datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        
        # Determine time-based greeting
        hour = now.hour
        if 5 <= hour < 12:
            time_greeting = "Good Morning! 🌅"
        elif 12 <= hour < 17:
            time_greeting = "Good Afternoon! ☀️"
        elif 17 <= hour < 21:
            time_greeting = "Good Evening! 🌆"
        else:
            time_greeting = "Good Night! 🌙"
        
        # ✅ Fixed: Get user's current balance/stats with correct parameter order
        try:
            total_bet, total_win = get(number, db=db) or (0, 0)
            balance = total_win - total_bet
            balance_info = f"\n💰 Your Balance: ₹{balance}"
        except Exception as e:
            print(f"❌ Error getting balance in greeting: {e}")
            balance_info = ""
        
        # Get next upcoming event
        try:
            next_event, next_session = get_next_event()
            event_info = f"\n🎯 Next Event: {next_event.EventCode} {next_session.upper()}"
            
            if next_session == "open":
                time_left = f" (Opens at {next_event.OpenTime})"
            else:
                time_left = f" (Closes at {next_event.CloseTime})"
            
            event_info += time_left
        except Exception as e:
            print(f"❌ Error getting next event: {e}")
            event_info = ""
        
        # Get events status
        events_status = get_current_events_status()
        
        greeting_reply = (
            f"{time_greeting}\n"
            f"Welcome back! 👋\n"
            f"📅 Date: {current_date}\n"
            f"⏰ Time: {current_time}"
            f"{balance_info}"
            f"{event_info}\n\n"
            f"{events_status}\n\n"
            f"💡 Type your bets or 'help' for commands!"
        )
        
        return greeting_reply
        
    except Exception as e:
        print(f"❌ Error generating greeting: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return (
            f"Hello! 👋\n"
            f"Welcome to the betting system!\n"
            f"⏰ Current time: {dt.datetime.now().strftime('%H:%M')}\n"
            f"Type 'help' for available commands."
        )

def get_current_events_status():
    """Get status of all events"""
    try:
        now = dt.datetime.now().time()
        status_lines = []
        
        for code, event in events.items():
            if event.yet_to_open():
                status = f"⏳ Opens at {event.OpenTime}"
            elif event.yet_to_close():
                status = f"🟢 OPEN - Closes at {event.CloseTime}"
            else:
                status = f"🔴 CLOSED"
            
            status_lines.append(f"{event.EventCode}: {status}")
        
        return "📊 **Events Status:**\n" + "\n".join(status_lines)
        
    except Exception as e:
        print(f"❌ Error getting events status: {e}")
        return "📊 Events status unavailable"

def get_events_status():
    """Standalone function to get events status"""
    return get_current_events_status()

def is_betting_message(message):
    """Check if message is a betting message"""
    betting_indicators = ['=', '*', '+', 'tp ', 'sp ', 'dp ', 'kn', 'bd', 'bn', 'kd']
    delete_keywords = ['no', 'delete', 'del', 'remove', 'cancel']
    
    message_lower = message.lower()
    
    # Check for betting indicators or delete keywords
    return (any(indicator in message_lower for indicator in betting_indicators) or 
            any(keyword == message_lower.strip() for keyword in delete_keywords))

def get_help_message():
    """Generate help message"""
    str=""
    for event in events.values():
        str+=f"• `{event.EventCode}` - {event.title}\n"
    return (
        f"🤖 **Betting Bot Commands** 🤖\n\n"
        f"**🎯 BETTING:**\n"
        f"{str}"
        f"**📝 BET FORMATS:**\n"
        f"• `1=100` - Single number\n"
        f"• `1,2,3=100` - Multiple numbers\n"
        f"• `tp 5=100` - Triple Panna\n"
        f"• `sp 3=100` - Single Panna\n"
        f"• `dp 7=100` - Double Panna\n\n"
        f"**🗑️ DELETE BETS:**\n"
        f"Reply 'no' or 'delete' to your bet message\n\n"
        f"**💰 OTHER COMMANDS:**\n"
        f"• `balance` - Check balance\n"
        f"• `status` - Events status\n"
        f"• `help` - This message\n\n"
        f"⏰ Current time: {dt.datetime.now().strftime('%H:%M:%S')}"
    )

if __name__ == "__main__":
    # Test the module functions here if needed
    print(get_help_message())
    pass
