from event import Event, events
import datetime as dt
from add import add, get, delete_bet
import re

# Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): 2025-08-15 07:01:07
# Current User's Login: Jeetujc


def get_latest_event():
    """
    Get the event with the latest (last) close time of the day
    Returns: Event object with the latest close time
    """
    latest_event = None
    latest_time = dt.time(hour=0, minute=0)
    
    for event in events.values():
        if event.CloseTime > latest_time:
            latest_time = event.CloseTime
            latest_event = event
    
    print(f"DEBUG: Latest event is {latest_event.EventCode if latest_event else 'None'} with close time {latest_time}")
    return latest_event


def all_events_closed():
    """
    Check if all events are closed for the day
    FIXED: Properly handles post-midnight events
    """
    now = dt.datetime.now().time()
    
    print(f"DEBUG all_events_closed: Current time: {now}")
    
    # ✅ SPECIAL CASE: Check if latest event closes after midnight and is still open
    latest_event = get_latest_event()
    if latest_event and latest_event.CloseTime < dt.time(hour=1, minute=0):
        # Latest event closes after midnight (e.g., 00:08)
        if now < latest_event.CloseTime:
            print(f"DEBUG: Latest event {latest_event.EventCode} still open until {latest_event.CloseTime}")
            return False
    
    # ✅ REGULAR LOGIC: Check all events
    for event in events.values():
        # If any event's close time hasn't passed yet, return False
        if now < event.CloseTime:
            print(f"DEBUG: Event {event.EventCode} still open until {event.CloseTime}")
            return False
    
    print(f"DEBUG: All events are closed")
    return True


def convert_digit_for_ordering(digit):
    """Convert digit for ordering: 0 becomes 10, others stay same"""
    return 10 if digit == 0 else digit


def is_ascending_order(digits):
    """Check if digits are in ascending order with 0 treated as 10"""
    converted_digits = [convert_digit_for_ordering(d) for d in digits]
    return converted_digits == sorted(converted_digits)


def get_combinations():
    tp_dict = {}  # Triple Panna (all 3 digits same)
    sp_dict = {}  # Single Panna (all 3 digits different and in ascending order)
    dp_dict = {}  # Double Panna (exactly 2 digits same)

    for num in range(1000):
        s = f"{num:03d}"  # Zero-padded string like '001', '012'
        digits = [int(d) for d in s]
        digit_sum = sum(digits) % 10

        digit_counts = {}
        for digit in digits:
            digit_counts[digit] = digit_counts.get(digit, 0) + 1

        max_count = max(digit_counts.values())
        unique_digits = len(digit_counts)
        
        # ✅ FIXED: Check if digits are in ascending order (0 treated as 10)
        if is_ascending_order(digits):
            if max_count == 3:
                tp_dict.setdefault(digit_sum, []).append(s)
            elif max_count == 2:
                dp_dict.setdefault(digit_sum, []).append(s)
            elif unique_digits == 3:
                sp_dict.setdefault(digit_sum, []).append(s)

    return tp_dict, sp_dict, dp_dict


def is_valid_three_digit_bet(number_str):
    """
    Check if a 3-digit bet is valid (digits must be in ascending order with 0 > 9)
    
    Args:
        number_str: String representation of the number (e.g., "123", "120")
    
    Returns:
        bool: True if valid, False if invalid
    """
    if len(number_str) != 3:
        return True  # Not a 3-digit number, allow it
    
    try:
        # Convert to 3-digit padded format
        num = int(number_str)
        padded = f"{num:03d}"
        digits = [int(d) for d in padded]
        
        # Check if digits are in ascending order (0 treated as 10)
        is_valid = is_ascending_order(digits)
        
        # Convert digits for display in error message
        display_digits = [convert_digit_for_ordering(d) for d in digits]
        
        print(f"DEBUG: Validating 3-digit bet '{number_str}' -> '{padded}' -> digits {digits} -> ordering values {display_digits} -> Valid: {is_valid}")
        
        return is_valid
        
    except ValueError:
        return False


tp_map, sp_map, dp_map = get_combinations()


def get_next_event():
    """
    Get the next available event and session based on current time
    FIXED: Properly handles midnight crossover and post-midnight events
    """
    now = dt.datetime.now().time()
    
    print(f"DEBUG get_next_event: Current time: {now}")
    
    # ✅ SPECIAL CASE: Check if we're after midnight but latest event is still open
    latest_event = get_latest_event()
    if latest_event and latest_event.CloseTime < dt.time(hour=1, minute=0):
        # Latest event closes after midnight (e.g., 00:08)
        if now < latest_event.CloseTime:
            # We're between 00:00 and the close time
            print(f"DEBUG: Post-midnight, latest event {latest_event.EventCode} still open until {latest_event.CloseTime}")
            
            # Check if we're before open time or in close session
            if now < latest_event.OpenTime:
                return latest_event, "open"
            else:
                return latest_event, "close"
    
    # ✅ REGULAR LOGIC: Create a list of all times (both open and close)
    all_times = []
    for event in events.values():
        all_times.append((event.OpenTime, event, "open"))
        all_times.append((event.CloseTime, event, "close"))
    
    # Sort by time
    all_times.sort(key=lambda x: x[0])
    
    # Find the next closest time
    for time, event, action in all_times:
        print(f"DEBUG: Checking {event.EventCode} {action} at {time}")
        if time > now:
            print(f"DEBUG: Selected {event.EventCode} {action}")
            return event, action
    
    # If no events found, wrap around to the first event of the day
    first_time, first_event, first_action = all_times[0]
    print(f"DEBUG: No more events today, wrapping to {first_event.EventCode} {first_action}")
    return first_event, first_action


def can_delete_bet(event_code, session):
    """
    Check if a bet can be deleted based on current time and event schedule
    
    SPECIAL RULE: If an event closes after midnight (e.g., 00:08), deletion is allowed 
    until that event's close time. All other events follow the 00:20 cutoff rule.
    
    Args:
        event_code: Event code like 'kn', 'bd', etc.
        session: 'open' or 'close'
    
    Returns:
        Tuple: (can_delete: bool, reason: str)
    """
    try:
        if event_code not in events:
            return False, f"❌ Invalid event code: {event_code.upper()}"
        
        event = events[event_code]
        now = dt.datetime.now().time()
        
        print(f"DEBUG: Checking delete permission for {event_code.upper()} {session.upper()}")
        print(f"DEBUG: Current time: {now}")
        print(f"DEBUG: Event open time: {event.OpenTime}")
        print(f"DEBUG: Event close time: {event.CloseTime}")
        
        # ✅ SPECIAL HANDLING: Check if this event has a close time after midnight
        latest_event = get_latest_event()
        is_latest_event = (latest_event and latest_event.EventCode.lower() == event_code.lower())
        
        # Cutoff times
        cutoff_start = dt.time(hour=0, minute=0)
        cutoff_end = dt.time(hour=0, minute=20)
        
        print(f"DEBUG: Is latest event: {is_latest_event}")
        print(f"DEBUG: Latest event: {latest_event.EventCode if latest_event else 'None'}")
        
        # ✅ CRITICAL LOGIC: Handle deletion based on event timing
        if session == "open":
            # For OPEN session: Can delete only if current time is before open time
            if now < event.OpenTime:
                return True, "✅ Delete allowed - Open betting time not yet started"
            else:
                # Check if we're in the midnight period and it's NOT the latest event
                if cutoff_start <= now < cutoff_end:
                    if not is_latest_event:
                        return False, (
                            f"❌ Cannot delete - System maintenance period (00:00-00:20)\n"
                            f"⏰ Deletions will be available again after 00:20 (12:20 AM)"
                        )
                
                return False, (
                    f"❌ Cannot delete - {event.EventCode} open betting time has passed\n"
                    f"⏰ Open time was: {event.OpenTime.strftime('%H:%M:%S')}"
                )
                
        elif session == "close":
            # For CLOSE session: Can delete only if current time is before close time
            
            # ✅ SPECIAL CASE: If this is the latest event with close time after midnight
            if is_latest_event and event.CloseTime < dt.time(hour=1, minute=0):
                # This event closes after midnight (e.g., 00:08)
                print(f"DEBUG: Latest event with post-midnight close time detected")
                
                if now < event.CloseTime:
                    return True, (
                        f"✅ Delete allowed - Close betting time not yet ended\n"
                        f"⏰ Close time: {event.CloseTime.strftime('%H:%M:%S')}"
                    )
                else:
                    return False, (
                        f"❌ Cannot delete - {event.EventCode} close betting time has ended\n"
                        f"⏰ Close time was: {event.CloseTime.strftime('%H:%M:%S')}"
                    )
            
            # ✅ REGULAR EVENTS: Check if we're in maintenance window
            if cutoff_start <= now < cutoff_end:
                return False, (
                    f"❌ Cannot delete - System maintenance period (00:00-00:20)\n"
                    f"⏰ Deletions will be available again after 00:20 (12:20 AM)"
                )
            
            # Normal case: event doesn't cross midnight or isn't the latest
            if now < event.CloseTime:
                return True, "✅ Delete allowed - Close betting time not yet ended"
            else:
                return False, (
                    f"❌ Cannot delete - {event.EventCode} close betting time has ended\n"
                    f"⏰ Close time was: {event.CloseTime.strftime('%H:%M:%S')}"
                )
        
        else:
            return False, f"❌ Invalid session: {session}"
            
    except Exception as e:
        print(f"❌ Error checking delete permission: {e}")
        import traceback
        print(traceback.format_exc())
        return False, f"❌ Error checking delete permission: {str(e)}"


def is_daily_reset_period(allow_latest_event=False):
    """
    Check if current time is in the daily reset period (00:00 - 00:20)
    
    Args:
        allow_latest_event: If True, allows operations for the latest event even during reset
    
    Returns:
        bool: True if in reset period, False otherwise
    """
    now = dt.datetime.now().time()
    cutoff_start = dt.time(hour=0, minute=0)
    cutoff_end = dt.time(hour=0, minute=20)
    
    in_reset_period = cutoff_start <= now < cutoff_end
    
    if not in_reset_period:
        return False
    
    # If we're in reset period but allowing latest event, check if latest event is still open
    if allow_latest_event:
        latest_event = get_latest_event()
        if latest_event and latest_event.CloseTime < dt.time(hour=1, minute=0):
            # Latest event closes after midnight
            if now < latest_event.CloseTime:
                print(f"DEBUG: In reset period but latest event {latest_event.EventCode} still open until {latest_event.CloseTime}")
                return False  # Don't block if latest event is still open
    
    return True


def extract_bets_from_old_message(old_msg):
    """
    Extract betting information from a user's old message
    Returns: (event_code, session, bets_dict) or (None, None, {})
    """
    try:
        lines = [line.strip() for line in old_msg.split('\n') if line.strip()]
        if not lines:
            return None, None, {}
        
        # Check if first line contains event code or is a bet
        first_line = lines[0].lower()
        
        if any(char in first_line for char in ['=', '*', '+']):
            # First line is a bet, use current next event
            event, session = get_next_event()
            event_code = event.EventCode.lower()
            start_index = 0
        else:
            # First line should be event code
            parts = first_line.split()
            if not parts:
                return None, None, {}
                
            code = parts[0]
            codes = code[:2]
            codel = code[2:]
            
            if codes not in events:
                return None, None, {}
            
            event_code = codes
            
            # Determine session
            if codel in ("o", "open"):
                session = "open"
            elif codel in ("c", "close"):
                session = "close"
            else:
                # Default to current state
                event_obj = events[codes]
                if event_obj.yet_to_open():
                    session = "open"
                elif event_obj.yet_to_close():
                    session = "close"
                else:
                    return None, None, {}
            
            start_index = 1
        
        # Parse betting lines
        bets = {}
        for line_num, line in enumerate(lines[start_index:], start_index + 1):
            if any(char in line for char in ['=', '*', '+']):
                individual_bets = split_multiple_bets_in_line(line)
                
                for individual_bet in individual_bets:
                    line_bets, line_errors = parse_bet_line(individual_bet, line_num, session)
                    
                    for number, amount in line_bets.items():
                        bets[number] = bets.get(number, 0) + amount
        
        return event_code, session, bets
        
    except Exception as e:
        print(f"DEBUG: Error extracting bets from old message: {e}")
        return None, None, {}


def split_multiple_bets_in_line(line):
    """
    Split a line containing multiple bets, properly handling special modes
    """
    special_modes = ['tp', 'sp', 'dp', 'spdpt', 'spdptp']
    
    # Enhanced pattern to match both special modes and regular bets
    # (?:tp|sp|dp|spdpt|spdptp)\s+\w+[=*+]\d+ matches "tp 5=100"
    # \w+(?:[,.\-]\w+)*[=*+]\d+ matches "1,2,3=100" or "1=100"
    pattern = r'(?:(?:' + '|'.join(special_modes) + r')\s+\w+[=*+]\d+|\w+(?:[,.\-]\w+)*[=*+]\d+)'
    
    matches = re.findall(pattern, line, re.IGNORECASE)
    
    if matches:
        return matches
    else:
        return [line]


def parse_bet_line(line, line_num, session=None):
    """
    Enhanced parsing for bet lines with session-specific validation (0 > 9 ordering)
    """
    errors = []
    bets = {}
    
    try:
        # Replace * and + with = for normalization
        normalized_line = line.replace('*', '=').replace('+', '=')
        
        if '=' not in normalized_line:
            errors.append(f"Line {line_num}: Missing '=' sign in '{line}'")
            return bets, errors
            
        key_part, value_part = normalized_line.split('=', 1)
        
        try:
            value = int(value_part.strip())
        except ValueError:
            errors.append(f"Line {line_num}: Invalid amount '{value_part.strip()}' in '{line}'")
            return bets, errors
            
        key_parts = key_part.strip().split()
        
        # Special modes: tp, sp, dp, spdpt, spdptp
        if len(key_parts) == 2 and key_parts[0].lower() in ['tp', 'sp', 'dp', 'spdpt','spdptp']:
            mode = key_parts[0].lower()
            try:
                last_digit = int(key_parts[1])
                numbers_to_bet = []
                
                if mode == 'sp':
                    numbers_to_bet.extend(sp_map.get(last_digit, []))
                elif mode == 'dp':
                    numbers_to_bet.extend(dp_map.get(last_digit, []))
                elif mode == 'tp':
                    numbers_to_bet.extend(tp_map.get(last_digit, []))
                elif mode == 'spdpt' or mode == 'spdptp':
                    numbers_to_bet.extend(sp_map.get(last_digit, []))
                    numbers_to_bet.extend(dp_map.get(last_digit, []))
                    numbers_to_bet.extend(tp_map.get(last_digit, []))
                
                print(f"DEBUG: {mode.upper()} - Found {len(numbers_to_bet)} numbers for digit sum % 10 = {last_digit}")
                
                for number in numbers_to_bet:
                    bets[number] = bets.get(number, 0) + value
                    
            except ValueError:
                errors.append(f"Line {line_num}: Invalid digit '{key_parts[1]}' for {mode.upper()} in '{line}'")
                
        else:
            # Regular number bets with session-specific validation
            numbers_str = key_part.strip().replace('-', ',').replace('.', ',')
            number_list = [num.strip() for num in numbers_str.split(',') if num.strip()]
            
            if not number_list:
                errors.append(f"Line {line_num}: No valid numbers found in '{line}'")
                return bets, errors
                
            for num_str in number_list:
                try:
                    test_num = int(num_str)
                    if 0 <= test_num <= 999:
                        # ✅ NEW: Check session restrictions for 2-digit bets
                        if len(num_str) == 2:
                            if session and session.lower() == 'close':
                                errors.append(
                                    f"Line {line_num}: 2-digit bet '{num_str}' not allowed in CLOSE session. "
                                    f"2-digit bets are only allowed in OPEN session."
                                )
                                continue
                        
                        # ✅ Validate 3-digit bets for ascending order
                        if len(num_str) == 3:
                            if not is_valid_three_digit_bet(num_str):
                                padded = f"{test_num:03d}"
                                digits = [int(d) for d in padded]
                                ordering_values = [convert_digit_for_ordering(d) for d in digits]
                                errors.append(
                                    f"Line {line_num}: Invalid 3-digit bet '{num_str}' -> '{padded}' "
                                    f"(digits {digits} with ordering values {ordering_values} not in ascending order). "
                                    f"Valid examples: 123, 120, 890, 340. Invalid: 012, 210, 901"
                                )
                                continue
                        
                        # Keep original format (no padding for 1 or 2 digit)
                        formatted_num = num_str
                        bets[formatted_num] = bets.get(formatted_num, 0) + value
                        print(f"DEBUG: Valid bet - Number: {formatted_num}, Amount: {value}, Session: {session}")
                    else:
                        errors.append(f"Line {line_num}: Number '{num_str}' out of range (0-999) in '{line}'")
                except ValueError:
                    errors.append(f"Line {line_num}: Invalid number '{num_str}' in '{line}'")
                    
    except Exception as e:
        errors.append(f"Line {line_num}: Parsing error in '{line}' - {str(e)}")
        
    return bets, errors


def placebet(num, msg, db, replied_msg=None):
    """
    Enhanced placebet function with session-specific validation and time-restricted delete functionality
    
    Args:
        num: User's WhatsApp number
        msg: Current message content
        db: Database connection
        replied_msg: Content of the message being replied to (if any)
    """
    message = [line.strip() for line in msg.split('\n') if line.strip()]
    if not message:
        return "⚠️ Empty message received."

    first_line = message[0].lower().strip()
    
    now_dt = dt.datetime.now()
    now_time = now_dt.time()
    
    # ✅ CHECK FOR DELETE COMMANDS FIRST (before general reset period check)
    delete_keywords = ['no', 'delete', 'del', 'remove', 'cancel']
    
    if replied_msg and first_line in delete_keywords:
        print(f"DEBUG: Delete command detected: '{first_line}' replying to: '{replied_msg[:50]}...'")
        
        # Extract betting information from the replied message
        event_code, session, bets_to_delete = extract_bets_from_old_message(replied_msg)
        
        if not bets_to_delete:
            return "❌ No valid bets found in the replied message to delete."
        
        if not event_code or not session:
            return "❌ Could not determine event or session from the replied message."
        
        # ✅ CHECK TIME RESTRICTIONS FOR DELETE (this handles the special 00:08 case)
        can_delete, time_reason = can_delete_bet(event_code, session)
        
        if not can_delete:
            return (
                f"🚫 **DELETE NOT ALLOWED**\n\n"
                f"{time_reason}\n\n"
                f"⏰ Current time: {now_time.strftime('%H:%M:%S')}\n"
                f"📅 Event: {event_code.upper()} {session.upper()}"
            )
        
        # Call delete_bet function
        try:
            success, delete_message, remaining_total = delete_bet(num, bets_to_delete, event_code, session, db)
            
            if success:
                return (
                    f"🗑️ **DELETED BETS**\n\n"
                    f"📅 Event: {event_code.upper()} {session.upper()}\n"
                    f"{delete_message}\n\n"
                    f"⏰ Deleted at: {now_time.strftime('%H:%M:%S')}"
                )
            else:
                return delete_message
                
        except Exception as e:
            print(f"❌ Error deleting bet: {e}")
            import traceback
            print(traceback.format_exc())
            return "❌ Failed to delete bet. Please try again."
    
    # ✅ NOW check for reset period for NEW BETS (allow latest event exception)
    if is_daily_reset_period(allow_latest_event=False):
        # During 00:00-00:20, check if latest event is still accepting bets
        latest_event = get_latest_event()
        
        # Determine which event user is trying to bet on
        target_event_code = None
        target_event = None
        
        if any(char in first_line for char in ['=', '*', '+']):
            # First line is a bet, get next event
            try:
                target_event, session_check = get_next_event()
                target_event_code = target_event.EventCode.lower()
                print(f"DEBUG: User betting without event code, target: {target_event_code}")
            except Exception as e:
                print(f"DEBUG: Error getting next event: {e}")
        else:
            # First line might contain event code
            parts = first_line.split()
            if parts:
                code = parts[0]
                codes_check = code[:2]
                if codes_check in events:
                    target_event_code = codes_check
                    target_event = events[codes_check]
                    print(f"DEBUG: User specified event code: {target_event_code}")
        
        # Check if betting on latest event and it's still open
        is_betting_on_latest = False
        if latest_event and target_event and now_time < latest_event.CloseTime:
            is_betting_on_latest = (latest_event.EventCode.lower() == target_event.EventCode.lower())
            print(f"DEBUG: Is betting on latest event: {is_betting_on_latest}")
            print(f"DEBUG: Latest event: {latest_event.EventCode}, Target: {target_event.EventCode if target_event else 'None'}")
        
        if not is_betting_on_latest:
            return (
                "🚫 *System Maintenance Period*\n"
                "Betting is closed between 00:00 - 00:20 (12:00 AM - 12:20 AM).\n"
                f"⏰ Current time: {now_time.strftime('%H:%M:%S')}\n"
                "Please try again after 00:20."
            )
        else:
            print(f"DEBUG: Allowing bet on latest event {latest_event.EventCode} during maintenance window")
    
    # Check if all events are closed (but allow latest event exception)
    if all_events_closed():
        print("DEBUG: all_events_closed() returned True")
        
        # Check if latest event is still open (post-midnight scenario)
        latest_event = get_latest_event()
        if latest_event and latest_event.CloseTime < dt.time(hour=1, minute=0) and now_time < latest_event.CloseTime:
            print(f"DEBUG: All events marked closed but latest event {latest_event.EventCode} still open until {latest_event.CloseTime}")
            # Continue to allow betting on this event - don't block
        else:
            cutoff_start = dt.time(hour=0, minute=0)
            cutoff_end = dt.time(hour=0, minute=20)
            
            # After all events close, block until 00:20
            if cutoff_start <= now_time < cutoff_end:
                return (
                    "🚫 *Betting Closed*\n"
                    "All bets for today are closed. No new bets accepted until 00:20 (12:20 AM).\n"
                    f"⏰ Current time: {now_time.strftime('%H:%M:%S')}"
                )
            
            # After 00:20, show next day message
            if now_time >= cutoff_end:
                next_event, next_session = get_next_event()
                return (
                    "🚫 *Betting Closed*\n"
                    f"Today's betting is closed. Next event: {next_event.EventCode} {next_session.upper()}\n"
                    f"⏰ Current time: {now_time.strftime('%H:%M:%S')}"
                )
    
    # ✅ REST OF YOUR REGULAR BETTING LOGIC
    codes = None
    event = None
    session = None
    
    # CASE 1: First line is already a bet → use next upcoming event
    if any(char in first_line for char in ['=', '*', '+']):
        try:
            event, session = get_next_event()
            codes = event.EventCode.lower()
            start_index = 0
            print(f"DEBUG: No event code provided, using next event: {event.EventCode} ({session})")
        except Exception as e:
            print(f"DEBUG: Error getting next event: {e}")
            return "❌ Unable to determine next event. Please specify event code."
    
    # CASE 2: First line is event code/session → normal flow
    else:
        parts = first_line.split()
        code = parts[0]
        codes = code[:2]
        codel = code[2:] if len(code) > 2 else ""

        print(f"DEBUG: Parsing first line: '{first_line}' -> codes: '{codes}', codel: '{codel}'")

        if codes not in events:
            return f"❌ Invalid event code: {code.upper()}"

        event = events[codes]

        # Parse session from code suffix or second word
        if codel in ("o", "open"):
            session = "open"
            print(f"DEBUG: Explicit OPEN session from suffix")
        elif codel in ("c", "close"):
            session = "close"
            print(f"DEBUG: Explicit CLOSE session from suffix")
        elif len(parts) > 1:
            second_part = parts[1].lower()
            if second_part in ("o", "open"):
                session = "open"
                print(f"DEBUG: Explicit OPEN session from second word")
            elif second_part in ("c", "close"):
                session = "close"
                print(f"DEBUG: Explicit CLOSE session from second word")
        
        # Validate session timing if explicitly specified
        if session == "open":
            if not event.yet_to_open():
                return f"❌ Betting time is over for {event.EventCode} OPEN session (closes at {event.OpenTime.strftime('%H:%M:%S')})"
        elif session == "close":
            if not event.yet_to_close():
                return f"❌ Betting time is over for {event.EventCode} CLOSE session (closes at {event.CloseTime.strftime('%H:%M:%S')})"
        
        # Auto-detect session if not explicitly specified
        if session is None:
            print(f"DEBUG: No explicit session, auto-detecting for {codes}")
            print(f"DEBUG: yet_to_open(): {event.yet_to_open()}")
            print(f"DEBUG: yet_to_close(): {event.yet_to_close()}")
            
            if event.yet_to_open():
                session = "open"
                print(f"DEBUG: Auto-selected OPEN session")
            elif event.yet_to_close():
                session = "close"
                print(f"DEBUG: Auto-selected CLOSE session")
            else:
                return f"❌ Betting time is over for {event.EventCode}"

        start_index = 1
    
    print(f"DEBUG: Final session determined: {session} for event: {codes.upper()}")
    
    arr = {}
    all_errors = []

    for line_num, line in enumerate(message[start_index:], start_index + 1):
        print(f"DEBUG: Processing line {line_num}: '{line}' for {codes.upper()} {session}")
        
        if any(char in line for char in ['=', '*', '+']):
            # ✅ Split line into multiple bets if they exist in same line
            individual_bets = split_multiple_bets_in_line(line)
            
            for bet_index, individual_bet in enumerate(individual_bets):
                print(f"DEBUG: Processing bet {bet_index + 1} in line {line_num}: '{individual_bet}'")
                
                # ✅ PASS SESSION TO PARSE_BET_LINE
                line_bets, line_errors = parse_bet_line(individual_bet, line_num, session)
                
                # Add bets to main array
                for number, amount in line_bets.items():
                    arr[number] = arr.get(number, 0) + amount
                    
                # Collect errors
                all_errors.extend(line_errors)
        else:
            all_errors.append(f"Line {line_num}: No bet operator (=, *, +) found in '{line}'")

    print(f"DEBUG: Final betting array has {len(arr)} entries")

    # If there are errors, return them
    if all_errors:
        error_msg = "❌ **Parsing Errors Found:**\n" + "\n".join(all_errors)
        if arr:  # If some bets were parsed successfully
            error_msg += f"\n\n⚠️ {len(arr)} valid bets found, but errors prevent processing."
        return error_msg

    if not arr:
        return "⚠️ No valid bets found."

    c_total = sum(arr.values())
    prev_total = get(num, codes, session, db, True) or 0

    try:
        add(num, arr, codes, session, db)
    except Exception as e:
        print(f"❌ Error adding bet: {e}")
        import traceback
        print(traceback.format_exc())
        return "❌ Failed to place bet. Please try again."

    final_total = prev_total + c_total
    arr_lines = "\n".join(f"{num_key} = ₹{amt}" for num_key, amt in arr.items())
    
    return (
        f"✅ *{event.title} {session.upper()}*\n" 
        f"{arr_lines}\n"
        f"✅ OK\n"
        f"💰 Current bet = ₹{c_total}\n"
        f"💰 Total bet   = ₹{final_total}"
    )


if __name__ == "__main__":
    print(all_events_closed())
    # Example usage
    print(placebet("919999999999", "000=100\n00=200\n3=300", None))
