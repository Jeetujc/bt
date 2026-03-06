from event import Event, events
import datetime as dt
from add import add, get, delete_bet
import re

# Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): 2025-08-15 07:01:07
# Current User's Login: Jeetujc

# ─────────────────────────────────────────────
# HELPER: Any event closing before 01:00 is treated as post-midnight
# ─────────────────────────────────────────────
POST_MIDNIGHT_CUTOFF = dt.time(hour=1, minute=0)


def is_post_midnight(close_time):
    """Returns True if the event closes before 04:00 (post-midnight event)"""
    return close_time < POST_MIDNIGHT_CUTOFF


def get_latest_event():
    """
    Get the last event of the day.
    Post-midnight events (close time < 04:00, e.g. MB 00:08) always come last.
    """
    latest_event = None
    latest_time = dt.time(hour=0, minute=0)
    found_post_midnight = False

    for event in events.values():
        pm = is_post_midnight(event.CloseTime)

        if pm:
            # Post-midnight always beats any regular event
            if not found_post_midnight or event.CloseTime > latest_time:
                latest_time = event.CloseTime
                latest_event = event
                found_post_midnight = True
        elif not found_post_midnight:
            # Regular event only considered if no post-midnight found yet
            if event.CloseTime > latest_time:
                latest_time = event.CloseTime
                latest_event = event

    print(f"DEBUG: Latest event is {latest_event.EventCode if latest_event else 'None'} with close time {latest_time}")
    return latest_event


def all_events_closed():
    """
    Check if all events are closed for the day.
    Post-midnight events (close < 04:00) are treated as end-of-day.
    """
    now = dt.datetime.now().time()
    print(f"DEBUG all_events_closed: Current time: {now}")

    latest_event = get_latest_event()

    if latest_event and is_post_midnight(latest_event.CloseTime):
        # Post-midnight event exists (e.g. MB closes at 00:08)
        if not is_post_midnight(now):
            # We are in normal hours (04:00+), MB hasn't closed yet for tonight
            print(f"DEBUG: Normal hours, MB not closed yet")
            return False
        # We are in post-midnight hours (00:00 - 03:59)
        if now < latest_event.CloseTime:
            print(f"DEBUG: Post-midnight, MB still open until {latest_event.CloseTime}")
            return False
        # now >= MB close time → all done
        print(f"DEBUG: All events closed including MB")
        return True

    # No post-midnight event — regular logic
    for event in events.values():
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
    tp_dict = {}
    sp_dict = {}
    dp_dict = {}

    for num in range(1000):
        s = f"{num:03d}"
        digits = [int(d) for d in s]
        digit_sum = sum(digits) % 10

        digit_counts = {}
        for digit in digits:
            digit_counts[digit] = digit_counts.get(digit, 0) + 1

        max_count = max(digit_counts.values())
        unique_digits = len(digit_counts)

        if is_ascending_order(digits):
            if max_count == 3:
                tp_dict.setdefault(digit_sum, []).append(s)
            elif max_count == 2:
                dp_dict.setdefault(digit_sum, []).append(s)
            elif unique_digits == 3:
                sp_dict.setdefault(digit_sum, []).append(s)

    return tp_dict, sp_dict, dp_dict


def is_valid_three_digit_bet(number_str):
    if len(number_str) != 3:
        return True
    try:
        num = int(number_str)
        padded = f"{num:03d}"
        digits = [int(d) for d in padded]
        is_valid = is_ascending_order(digits)
        display_digits = [convert_digit_for_ordering(d) for d in digits]
        print(f"DEBUG: Validating 3-digit bet '{number_str}' -> '{padded}' -> digits {digits} -> ordering values {display_digits} -> Valid: {is_valid}")
        return is_valid
    except ValueError:
        return False


tp_map, sp_map, dp_map = get_combinations()

def get_next_event():
    now = dt.datetime.now()
    print(f"DEBUG get_next_event: Current time: {now.time()}")

    all_times = []

    for event in events.values():
        open_dt = dt.datetime.combine(now.date(), event.OpenTime)
        close_dt = dt.datetime.combine(now.date(), event.CloseTime)

        # Post-midnight times → push to next calendar day
        if is_post_midnight(event.CloseTime):
            close_dt += dt.timedelta(days=1)

        if is_post_midnight(event.OpenTime):
            open_dt += dt.timedelta(days=1)

        # ✅ KEY FIX: If we are currently in post-midnight hours (00:00-04:00)
        # regular events (opening at e.g. 13:44 today) are FUTURE but belong to
        # today's schedule — push them to tomorrow so post-midnight events come first
        if is_post_midnight(now.time()):
            if not is_post_midnight(event.OpenTime):
                open_dt += dt.timedelta(days=1)
            if not is_post_midnight(event.CloseTime):
                close_dt += dt.timedelta(days=1)

        all_times.append((open_dt, event, "open"))
        all_times.append((close_dt, event, "close"))

        print(f"DEBUG: Event {event.EventCode} open at {open_dt}, close at {close_dt}")

    all_times.sort(key=lambda x: x[0])

    for time, event, action in all_times:
        print(f"DEBUG: Checking {event.EventCode} {action} at {time}")
        if time > now:
            print(f"DEBUG: Selected {event.EventCode} {action}")
            return event, action

    first_time, first_event, first_action = all_times[0]
    print(f"DEBUG: Wrapping to {first_event.EventCode} {first_action}")
    return first_event, first_action



def can_delete_bet(event_code, session):
    """
    Check if a bet can be deleted based on current time and event schedule.

    Rules:
    - OPEN session: can delete only before open time
    - CLOSE session (regular): can delete before close time, blocked during 00:00-00:20
    - CLOSE session (post-midnight, e.g. MB 00:08):
        - Allow delete during normal evening hours (04:00+) before midnight
        - Allow delete after midnight but before close time (00:00 - 00:08)
        - Block after close time
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

        latest_event = get_latest_event()
        is_latest_event = (latest_event and latest_event.EventCode.lower() == event_code.lower())
        is_pm_event = (is_latest_event and is_post_midnight(event.CloseTime))

        cutoff_start = dt.time(hour=0, minute=0)
        cutoff_end = dt.time(hour=0, minute=20)

        print(f"DEBUG: Is latest event: {is_latest_event}")
        print(f"DEBUG: Is post-midnight event: {is_pm_event}")

        # ── OPEN SESSION ──────────────────────────────────────────────────────
        if session == "open":
            if now < event.OpenTime:
                return True, "✅ Delete allowed - Open betting time not yet started"
            else:
                if cutoff_start <= now < cutoff_end and not is_latest_event:
                    return False, (
                        f"❌ Cannot delete - System maintenance period (00:00-00:20)\n"
                        f"⏰ Deletions will be available again after 00:20 (12:20 AM)"
                    )
                return False, (
                    f"❌ Cannot delete - {event.EventCode} open betting time has passed\n"
                    f"⏰ Open time was: {event.OpenTime.strftime('%H:%M:%S')}"
                )

        # ── CLOSE SESSION ─────────────────────────────────────────────────────
        elif session == "close":

            if is_pm_event:
                # Post-midnight event (e.g. MB closes 00:08)
                print(f"DEBUG: Post-midnight close event detected")

                if not is_post_midnight(now):
                    # Normal hours (04:00+) → same evening, MB hasn't closed yet
                    return True, (
                        f"✅ Delete allowed - Close betting time not yet ended\n"
                        f"⏰ Close time: {event.CloseTime.strftime('%H:%M:%S')}"
                    )

                # Post-midnight hours (00:00 - 03:59)
                if now < event.CloseTime:
                    # e.g. 00:05 < 00:08 → still open
                    return True, (
                        f"✅ Delete allowed - Close betting time not yet ended\n"
                        f"⏰ Close time: {event.CloseTime.strftime('%H:%M:%S')}"
                    )

                # now >= close time (e.g. 00:08, 00:15) → closed
                return False, (
                    f"❌ Cannot delete - {event.EventCode} close betting time has ended\n"
                    f"⏰ Close time was: {event.CloseTime.strftime('%H:%M:%S')}"
                )

            # Regular event
            if cutoff_start <= now < cutoff_end:
                return False, (
                    f"❌ Cannot delete - System maintenance period (00:00-00:20)\n"
                    f"⏰ Deletions will be available again after 00:20 (12:20 AM)"
                )

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


def is_daily_reset_period(allow_latest_event=True):
    """
    Check if current time is in the daily reset period (00:00 - 00:20).
    If allow_latest_event=True, does NOT block if the post-midnight event is still open.
    """
    now = dt.datetime.now().time()
    cutoff_start = dt.time(hour=0, minute=0)
    cutoff_end = dt.time(hour=0, minute=20)

    in_reset_period = cutoff_start <= now < cutoff_end

    if not in_reset_period:
        return False

    if allow_latest_event:
        latest_event = get_latest_event()
        if latest_event and is_post_midnight(latest_event.CloseTime):
            if now < latest_event.CloseTime:
                print(f"DEBUG: In reset period but {latest_event.EventCode} still open until {latest_event.CloseTime}")
                return False  # Don't block — MB still open

    return True


def extract_bets_from_old_message(old_msg):
    try:
        lines = [line.strip() for line in old_msg.split('\n') if line.strip()]
        if not lines:
            return None, None, {}

        first_line = lines[0].lower()

        if any(char in first_line for char in ['=', '*', '+']):
            event, session = get_next_event()
            event_code = event.EventCode.lower()
            start_index = 0
        else:
            parts = first_line.split()
            if not parts:
                return None, None, {}

            code = parts[0]
            codes = code[:2]
            codel = code[2:]

            if codes not in events:
                return None, None, {}

            event_code = codes

            if codel in ("o", "open"):
                session = "open"
            elif codel in ("c", "close"):
                session = "close"
            else:
                event_obj = events[codes]
                if event_obj.yet_to_open():
                    session = "open"
                elif event_obj.yet_to_close():
                    session = "close"
                else:
                    return None, None, {}

            start_index = 1

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
    special_modes = ['tp', 'sp', 'dp', 'spdpt', 'spdptp']
    pattern = r'(?:(?:' + '|'.join(special_modes) + r')\s+\w+[=*+]\d+|\w+(?:[,.\-]\w+)*[=*+]\d+)'
    matches = re.findall(pattern, line, re.IGNORECASE)
    return matches if matches else [line]


def parse_bet_line(line, line_num, session=None):
    errors = []
    bets = {}

    try:
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

        if len(key_parts) == 2 and key_parts[0].lower() in ['tp', 'sp', 'dp', 'spdpt', 'spdptp']:
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
                elif mode in ('spdpt', 'spdptp'):
                    numbers_to_bet.extend(sp_map.get(last_digit, []))
                    numbers_to_bet.extend(dp_map.get(last_digit, []))
                    numbers_to_bet.extend(tp_map.get(last_digit, []))

                print(f"DEBUG: {mode.upper()} - Found {len(numbers_to_bet)} numbers for digit sum % 10 = {last_digit}")

                for number in numbers_to_bet:
                    bets[number] = bets.get(number, 0) + value

            except ValueError:
                errors.append(f"Line {line_num}: Invalid digit '{key_parts[1]}' for {mode.upper()} in '{line}'")

        else:
            numbers_str = key_part.strip().replace('-', ',').replace('.', ',')
            number_list = [num.strip() for num in numbers_str.split(',') if num.strip()]

            if not number_list:
                errors.append(f"Line {line_num}: No valid numbers found in '{line}'")
                return bets, errors

            for num_str in number_list:
                try:
                    test_num = int(num_str)
                    if 0 <= test_num <= 999:
                        if len(num_str) == 2:
                            if session and session.lower() == 'close':
                                errors.append(
                                    f"Line {line_num}: 2-digit bet '{num_str}' not allowed in CLOSE session. "
                                    f"2-digit bets are only allowed in OPEN session."
                                )
                                continue

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
    message = [line.strip() for line in msg.split('\n') if line.strip()]
    if not message:
        return "⚠️ Empty message received."

    first_line = message[0].lower().strip()

    now_dt = dt.datetime.now()
    now_time = now_dt.time()

    # ── DELETE COMMAND — always checked first, before any time block ──────────
    delete_keywords = ['no', 'delete', 'del', 'remove', 'cancel']

    if replied_msg and first_line in delete_keywords:
        print(f"DEBUG: Delete command detected: '{first_line}' replying to: '{replied_msg[:50]}...'")

        event_code, session, bets_to_delete = extract_bets_from_old_message(replied_msg)

        if not bets_to_delete:
            return "❌ No valid bets found in the replied message to delete."

        if not event_code or not session:
            return "❌ Could not determine event or session from the replied message."

        can_delete, time_reason = can_delete_bet(event_code, session)

        if not can_delete:
            return (
                f"🚫 **DELETE NOT ALLOWED**\n\n"
                f"{time_reason}\n\n"
                f"⏰ Current time: {now_time.strftime('%H:%M:%S')}\n"
                f"📅 Event: {event_code.upper()} {session.upper()}"
            )

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

    # ── RESET PERIOD CHECK (00:00 - 00:20, except when MB still open) ─────────
    if is_daily_reset_period(allow_latest_event=True):
        return (
            "🚫 *System Maintenance Period*\n"
            "Betting is closed between 00:00 - 00:20 (12:00 AM - 12:20 AM).\n"
            f"⏰ Current time: {now_time.strftime('%H:%M:%S')}\n"
            "Please try again after 00:20."
        )

    # ── ALL EVENTS CLOSED CHECK ───────────────────────────────────────────────
    if all_events_closed():
        print("DEBUG: all_events_closed() returned True")

        latest_event = get_latest_event()

        # Post-midnight: after MB closes but before 00:20 → maintenance window
        if latest_event and is_post_midnight(latest_event.CloseTime):
            if is_post_midnight(now_time) and now_time >= latest_event.CloseTime:
                cutoff_end = dt.time(hour=0, minute=20)

                if now_time < cutoff_end:
                    # 00:08 - 00:20 → maintenance, no betting
                    return (
                        "🚫 *Betting Closed*\n"
                        "All bets for today are closed. Betting resumes after 00:20.\n"
                        f"⏰ Current time: {now_time.strftime('%H:%M:%S')}"
                    )
                else:
                    # 00:20+ → next day betting starts, show next event
                    next_event, next_session = get_next_event()
                    return (
                        "🚫 *Betting Closed*\n"
                        f"Next event: {next_event.EventCode} {next_session.upper()}\n"
                        f"⏰ Current time: {now_time.strftime('%H:%M:%S')}"
                    )

        # No post-midnight event — normal end of day, show next event
        next_event, next_session = get_next_event()
        return (
            "🚫 *Betting Closed*\n"
            f"Today's betting is closed. Next event: {next_event.EventCode} {next_session.upper()}\n"
            f"⏰ Current time: {now_time.strftime('%H:%M:%S')}"
        )

    # ── REGULAR BETTING LOGIC ─────────────────────────────────────────────────
    codes = None
    event = None
    session = None

    # CASE 1: First line is a bet → auto-detect next event
    if any(char in first_line for char in ['=', '*', '+']):
        try:
            event, session = get_next_event()
            codes = event.EventCode.lower()
            start_index = 0
            print(f"DEBUG: No event code provided, using next event: {event.EventCode} ({session})")
        except Exception as e:
            print(f"DEBUG: Error getting next event: {e}")
            return "❌ Unable to determine next event. Please specify event code."

    # CASE 2: First line contains event code
    else:
        parts = first_line.split()
        code = parts[0]
        codes = code[:2]
        codel = code[2:] if len(code) > 2 else ""

        print(f"DEBUG: Parsing first line: '{first_line}' -> codes: '{codes}', codel: '{codel}'")

        if codes not in events:
            return f"❌ Invalid event code: {code.upper()}"

        event = events[codes]

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

        if session == "open":
            if not event.yet_to_open():
                return f"❌ Betting time is over for {event.EventCode} OPEN session (closes at {event.OpenTime.strftime('%H:%M:%S')})"
        elif session == "close":
            if not event.yet_to_close():
                return f"❌ Betting time is over for {event.EventCode} CLOSE session (closes at {event.CloseTime.strftime('%H:%M:%S')})"

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
            individual_bets = split_multiple_bets_in_line(line)
            for bet_index, individual_bet in enumerate(individual_bets):
                print(f"DEBUG: Processing bet {bet_index + 1} in line {line_num}: '{individual_bet}'")
                line_bets, line_errors = parse_bet_line(individual_bet, line_num, session)
                for number, amount in line_bets.items():
                    arr[number] = arr.get(number, 0) + amount
                all_errors.extend(line_errors)
        else:
            all_errors.append(f"Line {line_num}: No bet operator (=, *, +) found in '{line}'")

    print(f"DEBUG: Final betting array has {len(arr)} entries")

    if all_errors:
        error_msg = "❌ **Parsing Errors Found:**\n" + "\n".join(all_errors)
        if arr:
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
    arr_lines = "\n".join(f"{num_key} = {amt}" for num_key, amt in arr.items())

    return (
        f"✅ *{event.title} {session.upper()}*\n"
        f"{arr_lines}\n"
        f"✅ OK\n"
        f"💰 Current bet = ₹{c_total}\n"
        f"💰 Total bet   = ₹{final_total}"
    )


if __name__ == "__main__":
    print(placebet("919999999999", "000=100\n100=200\n3=300", None))