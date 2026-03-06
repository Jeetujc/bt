import mysql.connector
from datetime import datetime
from nump import parse
import json
import os

EVENT_TITLES = {}
EVENT_FILE = "events_config.json"
EVENT_FILE_MTIME = 0


def load_event_titles():
    global EVENT_TITLES, EVENT_FILE_MTIME
    try:
        mtime = os.path.getmtime(EVENT_FILE)

        # reload only if file changed
        if mtime != EVENT_FILE_MTIME:
            with open(EVENT_FILE, "r") as f:
                data = json.load(f)
                EVENT_TITLES = {k.lower(): v["name"] for k, v in data.items()}
                EVENT_FILE_MTIME = mtime
                print("🔄 Event titles reloaded")

    except Exception as e:
        print(f"⚠️ Failed loading events_config.json: {e}")


def get_event_title(code):
    load_event_titles()   # auto reload check
    return EVENT_TITLES.get(code.lower(), code.upper())

# Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): 2025-08-15 06:35:39
# Current User's Login: Jeetujc

def convert_digit_for_ordering(digit):
    """Convert digit for ordering: 0 becomes 10, others stay same"""
    return 10 if digit == 0 else digit

def is_ascending_order(digits):
    """Check if digits are in ascending order with 0 treated as 10"""
    converted_digits = [convert_digit_for_ordering(d) for d in digits]
    return converted_digits == sorted(converted_digits)

def sort_digits_with_zero_last(digits):
    """Sort digits with 0 treated as 10 (so 0 comes last)"""
    return sorted(digits, key=convert_digit_for_ordering)

def get_number_pattern(number_str):
    """
    Determine if a 3-digit number is SP, DP, or TP based on digit repetition
    
    Args:
        number_str: 3-digit number as string (e.g., "123", "117", "111")
    
    Returns:
        str: "SP", "DP", "TP", or "INVALID"
    """
    if len(number_str) != 3:
        return "INVALID"
    
    # Pad to ensure 3 digits for analysis
    padded = f"{int(number_str):03d}"
    digits = [int(d) for d in padded]
    
    # Count frequency of each digit
    digit_counts = {}
    for digit in digits:
        digit_counts[digit] = digit_counts.get(digit, 0) + 1
    
    # Get the maximum count and number of unique digits
    max_count = max(digit_counts.values())
    unique_digits = len(digit_counts)
    
    if max_count == 3:
        # All 3 digits same (111, 222, 777)
        return "TP"
    elif max_count == 2:
        # Exactly 2 digits same (117, 228, 344)
        return "DP"
    elif unique_digits == 3:
        # All 3 digits different (123, 456, 789)
        return "SP"
    else:
        return "INVALID"

def normalize_three_digit_key(bet_key):
    """
    Normalize bet keys for comparison:
    - 1-digit and 2-digit numbers: keep as-is
    - 3-digit numbers: ensure padded to 3 digits for comparison
    """
    if len(bet_key) == 3 and bet_key.isdigit():
        # Already 3 digits, ensure it's padded correctly for comparison
        normalized = f"{int(bet_key):03d}"
        return normalized
    elif len(bet_key) <= 2 and bet_key.isdigit():
        # 1 or 2 digit number - keep original format, don't pad
        return bet_key
    elif len(bet_key) < 3 and bet_key.isdigit():
        # This case handles numbers that might need padding for 3-digit comparison only
        # But for storage, we keep original format
        return bet_key
    else:
        # Not a pure digit number, return as is
        return bet_key
    
def update_user_winnings(db, user_id, win_amount):
    """Update user's total winnings in users table"""
    try:
        cursor = db.cursor()
        
        # Update total_win in users table
        update_query = """
        UPDATE users 
        SET total_win = COALESCE(total_win, 0) + %s
        WHERE id = %s
        """
        
        cursor.execute(update_query, (win_amount, user_id))
        db.commit()
        
        # Get updated total for verification
        check_query = "SELECT total_win FROM users WHERE id = %s"
        cursor.execute(check_query, (user_id,))
        result = cursor.fetchone()
        new_total = result[0] if result else 0
        
        print(f"✅ User ID {user_id}: Added ₹{win_amount}, New total: ₹{new_total}")
        
        return new_total
        
    except Exception as e:
        print(f"❌ Error updating user winnings: {e}")
        if db:
            db.rollback()
        return None

def get_open_result_for_notification(db, bet_name):
    """Get open result for close session notification format"""
    try:
        cursor = db.cursor()
        query = """
        SELECT number_1, number_2, number_3 
        FROM bet_tracking 
        WHERE bet_name = %s AND number_1 IS NOT NULL
        ORDER BY id DESC LIMIT 1
        """
        cursor.execute(query, (bet_name,))
        result = cursor.fetchone()
        
        if result and all(x is not None for x in result):
            # Sort with 0 > 9 rule
            sorted_numbers = sort_digits_with_zero_last(list(result))
            return int(''.join(map(str, sorted_numbers)))
        else:
            return 0  # Default if no open result found
            
    except Exception as e:
        print(f"❌ Error getting open result: {e}")
        return 0

def update(db, bet_name, session, number_1, number_2, number_3):
    """
    Update winning results and notify users
    
    Args:
        db: Database connection
        bet_name: Event name (KN)
        session: OPEN or CLOSE
        number_1, number_2, number_3: The 3 drawn numbers
    """
    try:
        print(f"🎯 Processing {bet_name} {session} results...")
        print(f"📊 Numbers: {number_1} {number_2} {number_3}")
        
        # Calculate result with 0 treated as 10 for ordering
        # Sort the 3 numbers with 0 coming last
        three_numbers = sort_digits_with_zero_last([number_1, number_2, number_3])
        result = int(''.join(map(str, three_numbers)))
        
        # Panna: Sum of all 3 numbers mod 10
        panna = (number_1 + number_2 + number_3) % 10
        
        print(f"🔢 Raw numbers: [{number_1}, {number_2}, {number_3}]")
        print(f"🔢 Sorted numbers (0 > 9): {three_numbers}")
        print(f"🔢 {session} Result: {result}")
        print(f"🔢 {session} Panna: {panna}")
        print(f"🔢 Panna calculation: ({number_1} + {number_2} + {number_3}) % 10 = {panna}")
        
        # Update bet_tracking table
        update_bet_tracking(db, bet_name, session, number_1, number_2, number_3)
        
        # Calculate jodi for CLOSE session
        jodi = None
        if session.upper() == 'CLOSE':
            # Get open panna from bet_tracking for JODI calculation
            cursor = db.cursor()
            get_open_query = """
            SELECT number_1, number_2, number_3 
            FROM bet_tracking 
            WHERE bet_name = %s AND number_1 IS NOT NULL
            ORDER BY id DESC LIMIT 1
            """
            cursor.execute(get_open_query, (bet_name,))
            open_data = cursor.fetchone()
            
            open_panna = 0
            if open_data and all(x is not None for x in open_data):
                open_panna = (open_data[0] + open_data[1] + open_data[2]) % 10
            
            # Calculate JODI from open_panna and close_panna
            jodi = open_panna * 10 + panna
            print(f"🔢 Open Panna: {open_panna}")
            print(f"🔢 Jodi: {jodi}")
        
        # 📢 FIRST: Send result notification to ALL users
        print(f"📢 Step 1: Sending result notification to all users...")
        send_result_notification_to_all_users(db, bet_name, session, result, panna, jodi)
        
        # 💰 SECOND: Process winnings and send winning notifications to winners only
        print(f"💰 Step 2: Processing winnings and notifying winners...")
        total_winners = 0
        total_win_amount = 0
        
        if session.upper() == 'OPEN':
            # OPEN session: Only process OPEN bets, no JODI checking
            winners, win_amount = process_open_winnings(db, bet_name, result, panna)
            total_winners = winners
            total_win_amount = win_amount
        elif session.upper() == 'CLOSE':
            # CLOSE session: Process CLOSE bets + check JODI in OPEN bets
            winners, win_amount = process_close_winnings(db, bet_name, result, panna)
            total_winners = winners
            total_win_amount = win_amount
        
        print(f"🎊 Results Summary:")
        print(f"   📢 Result notifications sent to all users")
        print(f"   💰 Total Winners: {total_winners}")
        print(f"   💵 Total Win Amount: ₹{total_win_amount}")
        print(f"✅ {bet_name} {session} results processed successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in update function: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return False
    
def process_open_winnings(db, bet_name, open_result, open_panna):
    """Process winnings for OPEN session - NO JODI checking here"""
    try:
        cursor = db.cursor()
        
        # Get all open bets for this event
        get_bets_query = """
        SELECT bs.user_id, u.phone_no, bs.bets, bs.total_amount
        FROM bet_slips bs
        JOIN users u ON bs.user_id = u.id
        WHERE bs.event_name = %s AND bs.bet_type = 'open'
        """
        cursor.execute(get_bets_query, (bet_name,))
        user_bets = cursor.fetchall()
        
        if not user_bets:
            print(f"📭 No open bets found for {bet_name}")
            return 0, 0
        
        print(f"🎰 Processing {len(user_bets)} users with open bets...")
        print(f"🔍 OPEN session: Checking only PATTI and PANNA wins (NO JODI)")
        
        total_winners = 0
        total_win_amount = 0
        
        for user_id, phone_no, bets_json, total_amount in user_bets:
            try:
                bets = json.loads(bets_json) if isinstance(bets_json, str) else bets_json
                
                # ✅ Calculate OPEN winnings (no JODI)
                winnings = calculate_open_winnings(bets, open_result, open_panna)
                
                if winnings['total_win'] > 0:
                    # Update user winnings in users table
                    new_total = update_user_winnings(db, user_id, winnings['total_win'])
                    
                    if new_total is not None:
                        # Send winning notification
                        send_winning_notification(db, phone_no, bet_name, 'OPEN', winnings, open_result, open_panna)
                        
                        total_winners += 1
                        total_win_amount += winnings['total_win']
                        
                        print(f"💰 {phone_no}: Won ₹{winnings['total_win']} (Total: ₹{new_total})")
                    
            except Exception as e:
                print(f"❌ Error processing user {phone_no}: {e}")
        
        return total_winners, total_win_amount
        
    except Exception as e:
        print(f"❌ Error in process_open_winnings: {e}")
        return 0, 0

def process_close_winnings(db, bet_name, close_result, close_panna):
    """Process winnings for CLOSE session + check JODI in OPEN bets"""
    try:
        cursor = db.cursor()
        
        # ✅ Get open panna from bet_tracking for JODI calculation
        get_open_query = """
        SELECT number_1, number_2, number_3 
        FROM bet_tracking 
        WHERE bet_name = %s AND number_1 IS NOT NULL
        ORDER BY id DESC LIMIT 1
        """
        cursor.execute(get_open_query, (bet_name,))
        open_data = cursor.fetchone()
        
        open_panna = 0
        if open_data and all(x is not None for x in open_data):
            open_panna = (open_data[0] + open_data[1] + open_data[2]) % 10
        
        # ✅ Calculate JODI from open_panna and close_panna
        jodi = open_panna * 10 + close_panna
        jodi_str = f"{jodi:02d}"
        
        print(f"🔢 Open Panna: {open_panna}")
        print(f"🔢 Close Panna: {close_panna}")
        print(f"🔢 Jodi: {jodi} -> Jodi String: '{jodi_str}'")
        
        # Get all OPEN bets to check for Jodi matches
        get_open_bets_query = """
        SELECT bs.user_id, u.phone_no, bs.bets, bs.total_amount
        FROM bet_slips bs
        JOIN users u ON bs.user_id = u.id
        WHERE bs.event_name = %s AND bs.bet_type = 'open'
        """
        cursor.execute(get_open_bets_query, (bet_name,))
        open_user_bets = cursor.fetchall()
        
        # Get all close bets for this event
        get_close_bets_query = """
        SELECT bs.user_id, u.phone_no, bs.bets, bs.total_amount
        FROM bet_slips bs
        JOIN users u ON bs.user_id = u.id
        WHERE bs.event_name = %s AND bs.bet_type = 'close'
        """
        cursor.execute(get_close_bets_query, (bet_name,))
        close_user_bets = cursor.fetchall()
        
        print(f"🎰 Processing CLOSE winnings...")
        print(f"📊 Found {len(close_user_bets)} users with close bets")
        print(f"📊 Found {len(open_user_bets)} users with open bets (for Jodi checking)")
        
        total_winners = 0
        total_win_amount = 0
        
        # ✅ 1. Process CLOSE session winnings (PATTI, PANNA, JODI in close bets)
        for user_id, phone_no, bets_json, total_amount in close_user_bets:
            try:
                bets = json.loads(bets_json) if isinstance(bets_json, str) else bets_json
                
                winnings = calculate_close_winnings(bets, close_result, close_panna, jodi)
                
                if winnings['total_win'] > 0:
                    # Update user winnings in users table
                    new_total = update_user_winnings(db, user_id, winnings['total_win'])
                    
                    if new_total is not None:
                        # Send winning notification
                        send_winning_notification(db, phone_no, bet_name, 'CLOSE', winnings, close_result, close_panna, jodi)
                        
                        total_winners += 1
                        total_win_amount += winnings['total_win']
                        
                        print(f"💰 {phone_no}: Won ₹{winnings['total_win']} (Total: ₹{new_total})")
                    
                    
            except Exception as e:
                print(f"❌ Error processing close user {phone_no}: {e}")
        
        # ✅ 2. Check OPEN bets for JODI matches (cross-session winnings)
        print(f"🔍 Checking OPEN bets for Jodi '{jodi_str}' matches...")
        
        for user_id, phone_no, bets_json, total_amount in open_user_bets:
            try:
                bets = json.loads(bets_json) if isinstance(bets_json, str) else bets_json
                
                # Check if this user has the Jodi bet in OPEN session
                cross_session_winnings = check_open_bets_for_jodi(bets, jodi_str)
                
                if cross_session_winnings['total_win'] > 0:
                    # Update user winnings in users table
                    new_total = update_user_winnings(db, user_id, cross_session_winnings['total_win'])
                    
                    if new_total is not None:
                        # Send Jodi winning notification
                        send_jodi_notification(db, phone_no, bet_name, cross_session_winnings, jodi_str, open_panna, close_panna, close_result)
                        
                        total_winners += 1
                        total_win_amount += cross_session_winnings['total_win']
                        
                        print(f"💰 {phone_no}: Cross-session Jodi win ₹{cross_session_winnings['total_win']} (Total: ₹{new_total})")
                    
            except Exception as e:
                print(f"❌ Error processing open user for Jodi {phone_no}: {e}")
        
        return total_winners, total_win_amount
        
    except Exception as e:
        print(f"❌ Error in process_close_winnings: {e}")
        return 0, 0

def check_open_bets_for_jodi(open_bets, jodi_str):
    """
    Check OPEN session bets for Jodi matches
    
    Args:
        open_bets: Dictionary of open bets
        jodi_str: Jodi as 2-digit string (e.g., "01", "10")
    
    Returns:
        Dictionary with winnings info
    """
    winnings = {
        'jodi': {},
        'total_win': 0
    }
    
    print(f"🔍 Checking OPEN bets for Jodi '{jodi_str}'")
    
    for bet_key, bet_amount in open_bets.items():
        bet_key = str(bet_key).strip()
        bet_amount = int(bet_amount)
        
        # Check if this is a 2-digit bet that matches the Jodi
        if len(bet_key) == 2 and bet_key.isdigit():
            if bet_key == jodi_str:
                win_amount = bet_amount * 90
                winnings['jodi'][bet_key] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ Cross-session Jodi win: OPEN bet '{bet_key}' = ₹{win_amount}")
            else:
                print(f"❌ Jodi no match: OPEN bet '{bet_key}' != '{jodi_str}'")
    
    return winnings

def calculate_open_winnings(bets, open_result, open_panna):
    """Calculate winnings for open session - NO JODI checking here"""
    winnings = {
        'patti': {},          # Single digit wins (1-digit)
        'single_panna': {},   # Single Panna wins (3-digit, all different)
        'double_panna': {},   # Double Panna wins (3-digit, 2 same)
        'triple_panna': {},   # Triple Panna wins (3-digit, all same)
        'total_win': 0
    }
    
    # Normalize the open result for 3-digit comparison
    normalized_open_result = f"{open_result:03d}"
    result_pattern = get_number_pattern(normalized_open_result)
    
    print(f"🔍 Open Result: {open_result} -> Normalized: {normalized_open_result}")
    print(f"🔍 Open Panna: {open_panna}")
    print(f"🔍 Result Pattern: {result_pattern}")
    
    for bet_key, bet_amount in bets.items():
        bet_key = str(bet_key).strip()
        bet_amount = int(bet_amount)
        
        print(f"🎯 Checking bet: '{bet_key}' = ₹{bet_amount}")
        
        # PATTI (1-digit) - matches with open_panna
        if len(bet_key) == 1 and bet_key.isdigit():
            if int(bet_key) == open_panna:
                win_amount = bet_amount * 9
                winnings['patti'][bet_key] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ PATTI win: {bet_key} = ₹{win_amount}")
            else:
                print(f"❌ PATTI no match: {bet_key} != {open_panna}")
        
        # ✅ JODI (2-digit) - NO immediate winning in OPEN (will be checked during CLOSE)
        elif len(bet_key) == 2 and bet_key.isdigit():
            print(f"🎯 JODI bet: {bet_key} - Will be checked for Jodi during CLOSE session")
        
        # PANNA (3-digit) - matches with open result, determined by pattern
        elif len(bet_key) == 3 and bet_key.isdigit():
            # For 3-digit comparison, normalize both sides
            bet_as_padded = f"{int(bet_key):03d}"
            bet_pattern = get_number_pattern(bet_as_padded)
            
            print(f"🎯 PANNA bet: '{bet_key}' -> Padded: '{bet_as_padded}' -> Pattern: {bet_pattern}")
            print(f"🎯 Comparing with result: '{normalized_open_result}' -> Pattern: {result_pattern}")
            
            if bet_as_padded == normalized_open_result:
                # Determine win amount based on pattern
                if bet_pattern == "SP":  # Single Panna (all different)
                    win_amount = bet_amount * 150
                    winnings['single_panna'][bet_key] = {
                        'bet_amount': bet_amount,
                        'win_amount': win_amount
                    }
                    winnings['total_win'] += win_amount
                    print(f"✅ SP (Single Panna) win: {bet_key} = ₹{win_amount}")
                elif bet_pattern == "DP":  # Double Panna (2 same)
                    win_amount = bet_amount * 300
                    winnings['double_panna'][bet_key] = {
                        'bet_amount': bet_amount,
                        'win_amount': win_amount
                    }
                    winnings['total_win'] += win_amount
                    print(f"✅ DP (Double Panna) win: {bet_key} = ₹{win_amount}")
                elif bet_pattern == "TP":  # Triple Panna (all same)
                    win_amount = bet_amount * 600
                    winnings['triple_panna'][bet_key] = {
                        'bet_amount': bet_amount,
                        'win_amount': win_amount
                    }
                    winnings['total_win'] += win_amount
                    print(f"✅ TP (Triple Panna) win: {bet_key} = ₹{win_amount}")
            else:
                print(f"❌ PANNA no match: {bet_as_padded} != {normalized_open_result}")
        
        # Special mode handling with prefixes
        elif bet_key.startswith('sp_') or bet_key.startswith('SP_'):
            sp_number = bet_key.split('_')[1]
            sp_as_padded = f"{int(sp_number):03d}"
            if sp_as_padded == normalized_open_result:
                win_amount = bet_amount * 150
                winnings['single_panna'][sp_number] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ SP_ (Force Single Panna) win: {sp_number} = ₹{win_amount}")
        
        elif bet_key.startswith('dp_') or bet_key.startswith('DP_'):
            dp_number = bet_key.split('_')[1]
            dp_as_padded = f"{int(dp_number):03d}"
            if dp_as_padded == normalized_open_result:
                win_amount = bet_amount * 300
                winnings['double_panna'][dp_number] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ DP_ (Force Double Panna) win: {dp_number} = ₹{win_amount}")
        
        elif bet_key.startswith('tp_') or bet_key.startswith('TP_'):
            tp_number = bet_key.split('_')[1]
            tp_as_padded = f"{int(tp_number):03d}"
            if tp_as_padded == normalized_open_result:
                win_amount = bet_amount * 600
                winnings['triple_panna'][tp_number] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ TP_ (Force Triple Panna) win: {tp_number} = ₹{win_amount}")
    
    print(f"💰 Total winnings calculated: ₹{winnings['total_win']}")
    return winnings

def calculate_close_winnings(bets, close_result, close_panna, jodi):
    """Calculate winnings for close session with pattern-based panna detection"""
    winnings = {
        'patti': {},          # Single digit wins (1-digit)
        'single_panna': {},   # Single Panna wins (3-digit, all different)
        'double_panna': {},   # Double Panna wins (3-digit, 2 same)
        'triple_panna': {},   # Triple Panna wins (3-digit, all same)
        'jodi': {},           # Jodi wins (2-digit)
        'total_win': 0
    }
    
    # Normalize the close result for 3-digit comparison
    normalized_close_result = f"{close_result:03d}"
    jodi_str = f"{jodi:02d}"
    result_pattern = get_number_pattern(normalized_close_result)
    
    print(f"🔍 Close Result: {close_result} -> Normalized: {normalized_close_result}")
    print(f"🔍 Close Panna: {close_panna}")
    print(f"🔍 Jodi: {jodi} -> Jodi String: '{jodi_str}'")
    print(f"🔍 Result Pattern: {result_pattern}")
    
    for bet_key, bet_amount in bets.items():
        bet_key = str(bet_key).strip()
        bet_amount = int(bet_amount)
        
        print(f"🎯 Checking bet: '{bet_key}' = ₹{bet_amount}")
        
        # PATTI (1-digit) - matches with close_panna
        if len(bet_key) == 1 and bet_key.isdigit():
            if int(bet_key) == close_panna:
                win_amount = bet_amount * 9
                winnings['patti'][bet_key] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ PATTI win: {bet_key} = ₹{win_amount}")
            else:
                print(f"❌ PATTI no match: {bet_key} != {close_panna}")
        
        # JODI (2-digit) - matches with jodi (in CLOSE session)
        elif len(bet_key) == 2 and bet_key.isdigit():
            if bet_key == jodi_str:
                win_amount = bet_amount * 90
                winnings['jodi'][bet_key] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ JODI win (CLOSE): {bet_key} = ₹{win_amount}")
            else:
                print(f"❌ JODI no match (CLOSE): {bet_key} != {jodi_str}")
        
        # PANNA (3-digit) - matches with close result, determined by pattern
        elif len(bet_key) == 3 and bet_key.isdigit():
            # For 3-digit comparison, normalize both sides
            bet_as_padded = f"{int(bet_key):03d}"
            bet_pattern = get_number_pattern(bet_as_padded)
            
            print(f"🎯 PANNA bet: '{bet_key}' -> Padded: '{bet_as_padded}' -> Pattern: {bet_pattern}")
            print(f"🎯 Comparing with result: '{normalized_close_result}' -> Pattern: {result_pattern}")
            
            if bet_as_padded == normalized_close_result:
                # Determine win amount based on pattern
                if bet_pattern == "SP":  # Single Panna (all different)
                    win_amount = bet_amount * 150
                    winnings['single_panna'][bet_key] = {
                        'bet_amount': bet_amount,
                        'win_amount': win_amount
                    }
                    winnings['total_win'] += win_amount
                    print(f"✅ SP (Single Panna) win: {bet_key} = ₹{win_amount}")
                elif bet_pattern == "DP":  # Double Panna (2 same)
                    win_amount = bet_amount * 300
                    winnings['double_panna'][bet_key] = {
                        'bet_amount': bet_amount,
                        'win_amount': win_amount
                    }
                    winnings['total_win'] += win_amount
                    print(f"✅ DP (Double Panna) win: {bet_key} = ₹{win_amount}")
                elif bet_pattern == "TP":  # Triple Panna (all same)
                    win_amount = bet_amount * 600
                    winnings['triple_panna'][bet_key] = {
                        'bet_amount': bet_amount,
                        'win_amount': win_amount
                    }
                    winnings['total_win'] += win_amount
                    print(f"✅ TP (Triple Panna) win: {bet_key} = ₹{win_amount}")
            else:
                print(f"❌ PANNA no match: {bet_as_padded} != {normalized_close_result}")
        
        # Special mode handling with prefixes
        elif bet_key.startswith('sp_') or bet_key.startswith('SP_'):
            sp_number = bet_key.split('_')[1]
            sp_as_padded = f"{int(sp_number):03d}"
            if sp_as_padded == normalized_close_result:
                win_amount = bet_amount * 150
                winnings['single_panna'][sp_number] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ SP_ (Force Single Panna) win: {sp_number} = ₹{win_amount}")
        
        elif bet_key.startswith('dp_') or bet_key.startswith('DP_'):
            dp_number = bet_key.split('_')[1]
            dp_as_padded = f"{int(dp_number):03d}"
            if dp_as_padded == normalized_close_result:
                win_amount = bet_amount * 300
                winnings['double_panna'][dp_number] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ DP_ (Force Double Panna) win: {dp_number} = ₹{win_amount}")
        
        elif bet_key.startswith('tp_') or bet_key.startswith('TP_'):
            tp_number = bet_key.split('_')[1]
            tp_as_padded = f"{int(tp_number):03d}"
            if tp_as_padded == normalized_close_result:
                win_amount = bet_amount * 600
                winnings['triple_panna'][tp_number] = {
                    'bet_amount': bet_amount,
                    'win_amount': win_amount
                }
                winnings['total_win'] += win_amount
                print(f"✅ TP_ (Force Triple Panna) win: {tp_number} = ₹{win_amount}")
    
    print(f"💰 Total winnings calculated: ₹{winnings['total_win']}")
    return winnings

def send_result_notification_to_all_users(db, bet_name, session, result, panna, jodi=None):
    """Send result notification to all users in the system"""
    try:
        import requests
        from admin import load_config  # Import the load_config function
        
        # Load config to get all user phone numbers
        config = load_config()
        user_cuts = config.get("user_cuts", {})
        
        # Also get users from database
        cursor = db.cursor()
        get_all_users_query = "SELECT DISTINCT phone_no FROM users WHERE phone_no IS NOT NULL"
        cursor.execute(get_all_users_query)
        db_users = cursor.fetchall()
        
        # Combine phone numbers from config and database
        all_phone_numbers = set()
        
        # Add from config
        for phone_no in user_cuts.keys():
            all_phone_numbers.add(phone_no)
        
        # Add from database
        for (phone_no,) in db_users:
            if phone_no:
                all_phone_numbers.add(str(phone_no))
        
        print(f"📢 Sending result notification to {len(all_phone_numbers)} users...")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = f"✈️ LIVE RESULT ✈️\n"
        message += f"🎯 *{get_event_title(bet_name)} {session.upper()} *\n"
        
        if session.upper() == 'OPEN':
            # Format: 380/1 (result/panna) - BOLD and CENTERED
            message += f"                    *{result}/{panna}*\n\n"
        else:  # CLOSE
            # Format: 380/18/440 (open_result/jodi/close_result)
            open_result = get_open_result_for_notification(db, bet_name)
            jodi_str = f"{jodi:02d}" if jodi is not None else "00"
            message += f"               *{open_result}/{jodi_str}/{result}*\n\n"
        
        
        # Send to all users
        success_count = 0
        for phone_no in all_phone_numbers:
            try:
                response = requests.post('http://localhost:3003/send-message', json={
                    'number': phone_no,
                    'message': message
                })
                
                if response.status_code == 200:
                    success_count += 1
                    print(f"📱 Result notification sent to {phone_no}")
                else:
                    print(f"❌ Failed to send result notification to {phone_no}: Status {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error sending result notification to {phone_no}: {e}")
        
        print(f"✅ Result notifications sent successfully to {success_count}/{len(all_phone_numbers)} users")
        
    except Exception as e:
        print(f"❌ Error in send_result_notification_to_all_users: {e}")

def send_winning_notification(db, phone_no, bet_name, session, winnings, result, panna, jodi=None):
    """Send winning notification to user via WhatsApp with centralized format"""
    try:
        import requests
        
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        message = f"🎯 *{get_event_title(bet_name)} {session.lower()} RESULTS*\n"
        message += f"📅 {timestamp} UTC\n\n"
        
        if session.upper() == 'OPEN':
            # Format: 380/1 (result/panna) - BOLD and CENTERED
            message += f"                    *{result}/{panna}*\n\n"
        else:  # CLOSE
            # Format: 380/18/440 (open_result/jodi/close_result) - use actual close_result
            open_result = get_open_result_for_notification(db, bet_name)
            jodi_str = f"{jodi:02d}" if jodi is not None else "00"
            message += f"               *{open_result}/{jodi_str}/{result}*\n\n"
        
        # This is where you wanted the message = "" before - but we keep the result info
        # and add winning details below
        
        message += f"💰 *YOUR WINNINGS:*\n"
        
        # Add winning details with calculation format: "ANK: 1 : 100*9=900"
        if winnings.get('patti'):
            for num, win_data in winnings['patti'].items():
                bet_amt = win_data['bet_amount']
                win_amt = win_data['win_amount']
                message += f"🎯 *ANK: {num} : ₹{bet_amt}*9=₹{win_amt}*\n"
        
        if winnings.get('jodi'):
            for num, win_data in winnings['jodi'].items():
                bet_amt = win_data['bet_amount']
                win_amt = win_data['win_amount']
                message += f"🎯 *JODI: {num} : ₹{bet_amt}*90=₹{win_amt}*\n"
        
        if winnings.get('single_panna'):
            for num, win_data in winnings['single_panna'].items():
                bet_amt = win_data['bet_amount']
                win_amt = win_data['win_amount']
                message += f"🎯 *Single Panna: {num} : ₹{bet_amt}*150=₹{win_amt}*\n"
        
        if winnings.get('double_panna'):
            for num, win_data in winnings['double_panna'].items():
                bet_amt = win_data['bet_amount']
                win_amt = win_data['win_amount']
                message += f"🎯 *Double Panna: {num} : ₹{bet_amt}*300=₹{win_amt}*\n"
        
        if winnings.get('triple_panna'):
            for num, win_data in winnings['triple_panna'].items():
                bet_amt = win_data['bet_amount']
                win_amt = win_data['win_amount']
                message += f"🎯 *Triple Panna: {num} : ₹{bet_amt}*600=₹{win_amt}*\n"
        
        message += f"💵 *🎯TOTAL WIN: ₹{winnings['total_win']}*"
        
        # Send via WhatsApp API 
        response = requests.post('http://localhost:3003/send-message', json={
            'number': phone_no,
            'message': message
        })
        
        if response.status_code == 200:
            print(f"📱 Winning notification sent to {phone_no}")
        else:
            print(f"❌ Failed to send notification to {phone_no}: Status {response.status_code}")
        
    except Exception as e:
        print(f"❌ Error sending notification to {phone_no}: {e}")

def send_jodi_notification(db, phone_no, bet_name, winnings, jodi_str, open_panna, close_panna, close_result):
    """Send Jodi winning notification with updated format"""
    try:
        import requests
        
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        message = f"🎯 *{get_event_title(bet_name)} JODI RESULTS*\n"
        message += f"📅 {timestamp} UTC\n\n"
        
        # Format: open_result/jodi/close_result - use actual close_result
        open_result = get_open_result_for_notification(db, bet_name)
        message += f"               *{open_result}/{jodi_str}/{close_result}*\n\n"
        
        # This is where you wanted the message = "" before - but we keep the result info
        # and add winning details below
        
        message += f"💰 *YOUR WINNINGS:*\n"
        
        if winnings.get('jodi'):
            for num, win_data in winnings['jodi'].items():
                bet_amt = win_data['bet_amount']
                win_amt = win_data['win_amount']
                message += f"🎯 *JODI: {num} : ₹{bet_amt}*90=₹{win_amt}*\n"
        
        message += f"💵 *🎯TOTAL WIN: ₹{winnings['total_win']}*"
        
        # Send via WhatsApp API
        response = requests.post('http://localhost:3003/send-message', json={
            'number': phone_no,
            'message': message
        })
        
        if response.status_code == 200:
            print(f"📱 Jodi notification sent to {phone_no}")
        else:
            print(f"❌ Failed to send Jodi notification to {phone_no}: Status {response.status_code}")
        
    except Exception as e:
        print(f"❌ Error sending Jodi notification to {phone_no}: {e}")
        

def update_bet_tracking(db, bet_name, session, n1, n2, n3):
    """Update the bet_tracking table with results - single record for bet_name"""
    try:
        cursor = db.cursor()
        
        if session.upper() == 'OPEN':
            # Check if record exists for this bet_name
            check_query = "SELECT id FROM bet_tracking WHERE bet_name = %s"
            cursor.execute(check_query, (bet_name,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record with open numbers
                update_query = """
                UPDATE bet_tracking 
                SET number_1 = %s, number_2 = %s, number_3 = %s 
                WHERE bet_name = %s
                """
                cursor.execute(update_query, (n1, n2, n3, bet_name))
            else:
                # Insert new record with open numbers
                insert_query = """
                INSERT INTO bet_tracking (bet_name, number_1, number_2, number_3)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_query, (bet_name, n1, n2, n3))
        
        else:  # CLOSE
            # Check if record exists for this bet_name
            check_query = "SELECT id FROM bet_tracking WHERE bet_name = %s"
            cursor.execute(check_query, (bet_name,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record with close numbers
                update_query = """
                UPDATE bet_tracking 
                SET number_4 = %s, number_5 = %s, number_6 = %s 
                WHERE bet_name = %s
                """
                cursor.execute(update_query, (n1, n2, n3, bet_name))
            else:
                # Insert new record with close numbers only
                insert_query = """
                INSERT INTO bet_tracking (bet_name, number_4, number_5, number_6)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_query, (bet_name, n1, n2, n3))
        
        db.commit()
        print(f"✅ Results saved to bet_tracking table")
        
    except Exception as e:
        print(f"❌ Error updating bet_tracking: {e}")
