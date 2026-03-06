import json
import os
import re
from datetime import datetime
from event import admin_update_event_command, events

# Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): 2025-08-15 07:01:07
# Current User's Login: Jeetujc

CONFIG_FILE = 'config.json'

def get_data(command, db):
    """Get and aggregate data from bet slips with user cuts applied"""
    parts = command.split()
    
    if len(parts) != 3:
        return "Invalid command. Use format: get_data event_name open/close"
        
    event_name = parts[1].upper()
    bet_type = parts[2].lower()
    
    if bet_type not in ['open', 'close']:
        return "Invalid bet type. Use 'open' or 'close'"
    
    from admin import get_cut_for_number
    
    query = """
        SELECT bs.bets, u.phone_no
        FROM bet_slips bs
        JOIN users u ON bs.user_id = u.id
        WHERE bs.event_name = %s AND bs.bet_type = %s
    """
    
    cursor = db.cursor()
    cursor.execute(query, (event_name, bet_type))
    results = cursor.fetchall()
    
    if not results:
        return f"No bet slips found for {event_name} {bet_type}"
    
    combined_bets = {}
    for row in results:
        bets_json, phone_no = row
        bet_data = json.loads(bets_json) if isinstance(bets_json, str) else bets_json
        
        user_cut = get_cut_for_number(phone_no)
        
        for number, amount in bet_data.items():
            original_amount = float(amount)
            adjusted_amount = original_amount * (1 - user_cut)
            combined_bets[number] = combined_bets.get(number, 0) + adjusted_amount

    if not combined_bets:
        return f"No bets found for {event_name} {bet_type}"

    cutoff = 0.5 if event_name in ['BD', 'KD', 'BN', 'KN'] else 1

    # ── OPEN logic ────────────────────────────────────────────────
    if bet_type == 'open':
        single_totals = {}
        panna_bets = {}

        for number, amount in combined_bets.items():
            final_amount = int(amount * cutoff)
            d = len(number)

            if d == 1:
                single_totals[number] = single_totals.get(number, 0) + final_amount

            elif d == 2:
                # 12/10 = 1 → add amount to digit 1
                digit = str(int(number) // 10)
                single_totals[digit] = single_totals.get(digit, 0) + final_amount

            elif d == 3:
                panna_bets[number] = panna_bets.get(number, 0) + final_amount

        output_lines = []
        total_amount = 0

        digit_sum = 0
        for d in sorted(single_totals.keys()):
            amt = single_totals[d]
            output_lines.append(f"{d}={amt}")
            digit_sum += amt
            total_amount += amt
        if single_totals and event_name not in ['BD', 'KD', 'BN', 'KN']:
            output_lines.append(f"Total 1 digit = {digit_sum}")

        panna_sum = 0
        for number in sorted(panna_bets.keys(), key=lambda x: (len(x), x)):
            amt = panna_bets[number]
            output_lines.append(f"{number}={amt}")
            panna_sum += amt
            total_amount += amt
        if panna_bets and event_name not in ['BD', 'KD', 'BN', 'KN']:
            output_lines.append(f"Total 3 digit = {panna_sum}")

        output_lines.append(f"Total Amount = {total_amount}")
        return "\n".join(output_lines)

    # ── CLOSE logic ───────────────────────────────────────────────
    else:
        get_open_query = """
            SELECT number_1, number_2, number_3 
            FROM bet_tracking 
            WHERE bet_name = %s AND number_1 IS NOT NULL
            ORDER BY id DESC LIMIT 1
        """
        cursor.execute(get_open_query, (event_name,))
        open_data = cursor.fetchone()

        if not open_data or any(v is None for v in open_data):
            return "⚠️ Open result not found — cannot process close bets"

        aa = (int(open_data[0]) + int(open_data[1]) + int(open_data[2])) % 10

        single_totals = {}
        panna_bets = {}

        for number, amount in combined_bets.items():
            final_amount = int(amount * cutoff)
            d = len(number)

            if d == 1:
                single_totals[number] = single_totals.get(number, 0) + final_amount

            elif d == 2:
                # if 12//10 == aa → last digit (2) gets amount*9
                if int(number) // 10 == aa:
                    last_digit = str(int(number) % 10)
                    payout = final_amount * 9
                    single_totals[last_digit] = single_totals.get(last_digit, 0) + payout
                # else ignore

            elif d == 3:
                panna_bets[number] = panna_bets.get(number, 0) + final_amount

        output_lines = []
        total_amount = 0

        digit_sum = 0
        for d in sorted(single_totals.keys()):
            amt = single_totals[d]
            output_lines.append(f"{d}={amt}")
            digit_sum += amt
            total_amount += amt
        if single_totals and event_name not in ['BD', 'KD', 'BN', 'KN']:
            output_lines.append(f"Total 1 digit = {digit_sum}")

        panna_sum = 0
        for number in sorted(panna_bets.keys(), key=lambda x: (len(x), x)):
            amt = panna_bets[number]
            output_lines.append(f"{number}={amt}")
            panna_sum += amt
            total_amount += amt
        if panna_bets and event_name not in ['BD', 'KD', 'BN', 'KN']:
            output_lines.append(f"Total 3 digit = {panna_sum}")

        output_lines.append(f"Total Amount = {total_amount}")
        return "\n".join(output_lines)
    
def load_config():
    """Load configuration from JSON file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as file:
                return json.load(file)
        else:
            # Create default config if file doesn't exist
            default_config = {
                "user_cuts": {
                    "918319592160": 15,
                    "916263163540": 20,
                    "917389545640": 10,
                    "917415241382": 12,
                    "917415432279": 18,
                    "919398311688": 14,
                    "918269254317": 16,
                    "6266782180": 13
                },
                "admin_users": ["916263163540"],
                "default_cut": 10
            }
            save_config(default_config)
            return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def save_config(config):
    """Save configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w') as file:
            json.dump(config, file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def normalize_phone_number(phone_no):
    """
    Normalize phone number by removing country codes and prefixes
    
    Args:
        phone_no: Phone number in any format
    
    Returns:
        str: Normalized phone number
    """
    phone_str = str(phone_no).strip()
    
    # Remove +91 or 91 prefix if present
    if phone_str.startswith('+91'):
        phone_str = phone_str[3:]
    elif phone_str.startswith('91') and len(phone_str) > 10:
        phone_str = phone_str[2:]
    
    return phone_str

def is_admin(phone_no):
    """Check if phone number is admin"""
    try:
        config = load_config()
        admin_users = config.get('admin_users', [])
        
        normalized_phone = normalize_phone_number(phone_no)
        
        for admin in admin_users:
            normalized_admin = normalize_phone_number(admin)
            if normalized_phone == normalized_admin:
                return True
        return False
    except Exception:
        return False

def is_user_allowed(phone_number):
    """Check if user is allowed (has a cut configured)"""
    try:
        config = load_config()
        user_cuts = config.get('user_cuts', {})
        
        normalized_phone = normalize_phone_number(phone_number)
        
        # Check if user exists in user_cuts
        for stored_number in user_cuts.keys():
            normalized_stored = normalize_phone_number(stored_number)
            if normalized_phone == normalized_stored:
                return True
        
        return False
        
    except Exception:
        return False

def get_cut_for_number(phone_number):
    """Get cut percentage for a specific number"""
    try:
        config = load_config()
        user_cuts = config.get('user_cuts', {})
        default_cut = config.get('default_cut', 10)
        
        normalized_phone = normalize_phone_number(phone_number)
        
        # Try to find user's cut
        for stored_number, cut in user_cuts.items():
            normalized_stored = normalize_phone_number(stored_number)
            if normalized_phone == normalized_stored:
                return cut / 100 if cut > 1 else cut
        
        # Return default
        return default_cut / 100 if default_cut > 1 else default_cut
        
    except Exception as e:
        print(f"Error getting cut for {phone_number}: {e}")
        return 0.10

def handle_admin_command(phone_no, message,db):
    """
    Handle admin commands from WhatsApp
    
    Args:
        phone_no: Clean phone number (without @c.us)
        message: Command message
    
    Returns:
        str: Reply message
    """
    if not is_admin(phone_no):
        return "❌ You are not authorized to use admin commands."
    
    message = message.strip()
    message_lower = message.lower()
    
    try:
        # ✅ Events Management Commands
        if message_lower.startswith('events '):
            event_command = message[7:]  # Remove 'events ' prefix
            return admin_update_event_command(events, event_command)
        
        # Help command
        elif message_lower == 'help' or message_lower == 'admin help':
            return get_admin_help()
        
        # List all users and cuts
        elif message_lower == 'list' or message_lower == 'list users':
            return list_all_users()
        
        # Add new user with cut
        elif message_lower.startswith('add '):
            return add_user(message_lower)
        
        # Update existing user cut
        elif message_lower.startswith('change '):
            return update_user(message_lower)
        
        # Remove user
        elif message_lower.startswith('remove '):
            return remove_user(message_lower)
        
        # Show specific user
        elif message_lower.startswith('show '):
            return show_user_info(message_lower)
        
        # Bulk operations
        elif message_lower.startswith('bulk '):
            return bulk_add_users(message_lower)

        elif message_lower.startswith('get_data'):
            return get_data(message_lower,db)

        else:
            return "❓ Unknown command. Send 'help' for available commands."
    
    except Exception as e:
        return f"❌ Error processing command: {str(e)}"

def get_admin_help():
    """Get admin help message"""
    return """🔧 **ADMIN COMMANDS**

**👥 USER MANAGEMENT:**
• `list` - Show all users and cuts
• `show 916263163540` - Show specific user info
• `add 916263163540 15` - Add user with 15% cut
• `change 916263163540 20` - Change user's cut to 20%
• `remove 916263163540` - Remove user
• `bulk 916263163540,15 917890123456,20` - Bulk add users

**⏰ EVENTS MANAGEMENT:**
• `events status` - Show events status
• `events update bd open 12:00` - Update event timing
• `events reload` - Reload events config
• `events help` - Events commands help

**💡 EXAMPLES:**
• Add user: `add 916263163540 15`
• Change cut: `change 916263163540 25`
• Update timing: `events update bd open 11:30`
• Check events: `events status`

📊 Users with cuts are automatically allowed! 🚀"""

def list_all_users():
    """List all users and their cuts"""
    try:
        config = load_config()
        user_cuts = config.get('user_cuts', {})
        admin_users = config.get('admin_users', [])
        
        if not user_cuts:
            return "📭 No users configured yet.\n\nSend `add <number> <cut>` to add users."
        
        message = "👥 **ALL USERS & CUTS**\n\n"
        
        for i, (number, cut) in enumerate(sorted(user_cuts.items()), 1):
            admin_mark = " 👑" if number in admin_users else ""
            message += f"{i}. `{number}` → {cut}%{admin_mark}\n"
        
        message += f"\n📊 Total: {len(user_cuts)} users"
        message += f"\n👑 Admins: {len(admin_users)}"
        return message
        
    except Exception as e:
        return f"❌ Error listing users: {str(e)}"

def add_user(command):
    """Add new user with cut"""
    try:
        # Parse: "add 916263163540 15"
        parts = command.split()
        if len(parts) != 3:
            return "❌ Format: `add <phone_number> <cut_percentage>`\nExample: `add 916263163540 15`"
        
        number = parts[1].strip()
        cut = float(parts[2].strip())
        
        if cut < 0 or cut > 100:
            return "❌ Cut percentage must be between 0 and 100"
        
        config = load_config()
        user_cuts = config.get('user_cuts', {})
        
        if number in user_cuts:
            return f"⚠️ User `{number}` already exists with {user_cuts[number]}% cut.\n\nUse `change {number} {cut}` to change it."
        
        user_cuts[number] = cut
        config['user_cuts'] = user_cuts
        
        if save_config(config):
            return f"✅ User added successfully!\n\n📱 `{number}` → {cut}% cut\n📊 Total users: {len(user_cuts)}\n\n🎯 User is now allowed to bet!"
        else:
            return "❌ Failed to save configuration"
            
    except ValueError:
        return "❌ Invalid cut percentage. Must be a number.\nExample: `add 916263163540 15`"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def update_user(command):
    """Update existing user's cut"""
    try:
        # Parse: "change 916263163540 20"
        parts = command.split()
        if len(parts) != 3:
            return "❌ Format: `change <phone_number> <new_cut>`\nExample: `change 916263163540 20`"
        
        number = parts[1].strip()
        new_cut = float(parts[2].strip())
        
        if new_cut < 0 or new_cut > 100:
            return "❌ Cut percentage must be between 0 and 100"
        
        config = load_config()
        user_cuts = config.get('user_cuts', {})
        
        if number not in user_cuts:
            return f"❌ User `{number}` not found.\n\nUse `add {number} {new_cut}` to add them."
        
        old_cut = user_cuts[number]
        user_cuts[number] = new_cut
        config['user_cuts'] = user_cuts
        
        if save_config(config):
            return f"✅ User updated successfully!\n\n📱 `{number}`\n🔄 {old_cut}% → {new_cut}%"
        else:
            return "❌ Failed to save configuration"
            
    except ValueError:
        return "❌ Invalid cut percentage. Must be a number."
    except Exception as e:
        return f"❌ Error: {str(e)}"

def remove_user(command):
    """Remove user"""
    try:
        # Parse: "remove 916263163540"
        parts = command.split()
        if len(parts) != 2:
            return "❌ Format: `remove <phone_number>`\nExample: `remove 916263163540`"
        
        number = parts[1].strip()
        
        config = load_config()
        user_cuts = config.get('user_cuts', {})
        
        if number not in user_cuts:
            return f"❌ User `{number}` not found."
        
        removed_cut = user_cuts[number]
        del user_cuts[number]
        config['user_cuts'] = user_cuts
        
        if save_config(config):
            return f"✅ User removed successfully!\n\n📱 `{number}` ({removed_cut}% cut)\n📊 Remaining users: {len(user_cuts)}\n\n⚠️ User can no longer bet!"
        else:
            return "❌ Failed to save configuration"
            
    except Exception as e:
        return f"❌ Error: {str(e)}"

def show_user_info(command):
    """Show specific user's information"""
    try:
        # Parse: "show 916263163540"
        parts = command.split()
        if len(parts) != 2:
            return "❌ Format: `show <phone_number>`\nExample: `show 916263163540`"
        
        number = parts[1].strip()
        
        config = load_config()
        user_cuts = config.get('user_cuts', {})
        admin_users = config.get('admin_users', [])
        
        message = f"📱 **USER INFO: {number}**\n\n"
        
        # Check if user exists
        if number in user_cuts:
            message += f"✅ Status: Allowed\n"
            message += f"💰 Cut: {user_cuts[number]}%\n"
        else:
            message += "❌ Status: Not Allowed\n"
            default_cut = config.get('default_cut', 10)
            message += f"💰 Cut: {default_cut}% (default)\n"
        
        # Check if admin
        if number in admin_users:
            message += "👑 Role: Admin\n"
        else:
            message += "👤 Role: User\n"
        
        return message
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

def bulk_add_users(command):
    """Bulk add multiple users with cuts"""
    try:
        # Parse: "bulk 916263163540,15 917890123456,20"
        command = command.replace('bulk ', '')
        pairs = command.split()
        
        if not pairs:
            return "❌ Format: `bulk <number1>,<cut1> <number2>,<cut2>`\nExample: `bulk 916263163540,15 917890123456,20`"
        
        config = load_config()
        user_cuts = config.get('user_cuts', {})
        
        added = []
        updated = []
        errors = []
        
        for pair in pairs:
            try:
                if ',' not in pair:
                    errors.append(f"Invalid format: {pair}")
                    continue
                
                number, cut_str = pair.split(',', 1)
                number = number.strip()
                cut = float(cut_str.strip())
                
                if cut < 0 or cut > 100:
                    errors.append(f"{number}: Cut must be 0-100")
                    continue
                
                if number in user_cuts:
                    old_cut = user_cuts[number]
                    user_cuts[number] = cut
                    updated.append(f"{number}: {old_cut}%→{cut}%")
                else:
                    user_cuts[number] = cut
                    added.append(f"{number}: {cut}%")
                    
            except ValueError:
                errors.append(f"Invalid cut for {number}")
            except Exception as e:
                errors.append(f"{pair}: {str(e)}")
        
        # Save changes
        if added or updated:
            config['user_cuts'] = user_cuts
            
            if save_config(config):
                result = "✅ **BULK UPDATE COMPLETE**\n\n"
                
                if added:
                    result += f"➕ **ADDED ({len(added)}):**\n"
                    for item in added:
                        result += f"• {item}\n"
                    result += "\n"
                
                if updated:
                    result += f"🔄 **UPDATED ({len(updated)}):**\n"
                    for item in updated:
                        result += f"• {item}\n"
                    result += "\n"
                
                if errors:
                    result += f"❌ **ERRORS ({len(errors)}):**\n"
                    for error in errors:
                        result += f"• {error}\n"
                    result += "\n"
                
                result += f"📊 Total users: {len(user_cuts)}"
                return result
            else:
                return "❌ Failed to save configuration"
        else:
            return "❌ No valid changes made"
            
    except Exception as e:
        return f"❌ Error: {str(e)}"
