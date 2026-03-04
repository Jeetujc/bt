from nump import parse
import json

def add(wa_id, arr, bet_name, session, db):
    try:
        cursor = db.cursor()
        user_number = parse(wa_id)

        # Ensure user exists
        cursor.execute("""
            INSERT INTO users (phone_no) 
            VALUES (%s) 
            ON DUPLICATE KEY UPDATE phone_no = VALUES(phone_no)
        """, (user_number,))
        
        cursor.execute("SELECT id FROM users WHERE phone_no = %s", (user_number,))
        user_id = cursor.fetchone()[0]

        # Check if bet slip already exists (no date filter)
        cursor.execute("""
            SELECT id, bets, total_amount 
            FROM bet_slips 
            WHERE user_id = %s AND event_name = %s AND bet_type = %s
        """, (user_id, bet_name, session))
        
        existing_bet = cursor.fetchone()

        # Prepare new bets JSON and calculate totals
        new_bets_json = {}
        total_amount = 0
        bet_count = 0

        if existing_bet:
            # Update existing bet slip
            existing_id = existing_bet[0]
            existing_bets = json.loads(existing_bet[1]) if isinstance(existing_bet[1], str) else existing_bet[1]
            previous_total = existing_bet[2]
            
            # Merge existing bets with new bets
            merged_bets = {}
            for num, amount in existing_bets.items():
                merged_bets[str(num)] = int(amount)
            
            for num, amount in arr.items():
                if amount > 0:
                    num_str = str(num)
                    merged_bets[num_str] = merged_bets.get(num_str, 0) + amount
            
            # Remove zero amounts
            new_bets_json = {k: v for k, v in merged_bets.items() if v > 0}
            total_amount = sum(new_bets_json.values())
            bet_count = len(new_bets_json)
            
            # Calculate amount difference for user total update
            amount_difference = total_amount - previous_total
            
            # Update existing bet slip
            cursor.execute("""
                UPDATE bet_slips 
                SET bets = %s, total_amount = %s, bet_count = %s 
                WHERE id = %s
            """, (json.dumps(new_bets_json), total_amount, bet_count, existing_id))
            
            print(f"✅ Bet updated: User {user_number}, Event {bet_name}, Session {session}, Amount ₹{total_amount}")
            
        else:
            # Create new bet slip
            for num, amount in arr.items():
                if amount > 0:
                    num_str = str(num)
                    new_bets_json[num_str] = amount
                    total_amount += amount
                    bet_count += 1
            
            amount_difference = total_amount
            
            # Insert new bet slip
            if new_bets_json:
                cursor.execute("""
                    INSERT INTO bet_slips (user_id, event_name, bet_type, bets, total_amount, bet_count) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, bet_name, session, json.dumps(new_bets_json), total_amount, bet_count))
                
                print(f"✅ New bet added: User {user_number}, Event {bet_name}, Session {session}, Amount ₹{total_amount}")

        # Update user's total bet
        if amount_difference != 0:
            cursor.execute("""
                UPDATE users 
                SET total_bet = COALESCE(total_bet, 0) + %s 
                WHERE id = %s
            """, (amount_difference, user_id))

        db.commit()

    except Exception as e:
        db.rollback()
        print("❌ Error in add():", e)
        raise e

def get(wa_id, bet_name=None, session=None, db=None, get_total=False):
    """Get user bets/stats with proper error handling"""
    if db is None:
        print("❌ Database connection is None in get()")
        return None
    
    try:
        cursor = db.cursor()
        user_number = parse(wa_id)
        
        if bet_name is None and session is None:
            # Get total stats from users table
            cursor.execute("SELECT total_bet, total_win FROM users WHERE phone_no = %s", (user_number,))
            result = cursor.fetchone()
            
            if result is None:
                print(f"❌ User not found for phone: {user_number}")
                return (0, 0)  # Return default values for new user
            
            # Ensure we have proper values
            total_bet = result[0] if result[0] is not None else 0
            total_win = result[1] if result[1] is not None else 0
            
            print(f"✅ User stats: Total bet = ₹{total_bet}, Total win = ₹{total_win}")
            return (int(total_bet), int(total_win))
        
        elif bet_name is not None and session is not None and get_total:
            # Get current bet total for specific event and session
            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0) 
                FROM bet_slips 
                WHERE user_id = (SELECT id FROM users WHERE phone_no = %s) 
                AND event_name = %s 
                AND bet_type = %s
            """, (user_number, bet_name.lower(), session.lower()))
            
            result = cursor.fetchone()
            bet_total = result[0] if result and result[0] is not None else 0
            
            print(f"✅ {bet_name} {session} bet total: ₹{bet_total}")
            return int(bet_total)
        
        else:
            # Default case - return user stats
            cursor.execute("SELECT total_bet, total_win FROM users WHERE phone_no = %s", (user_number,))
            result = cursor.fetchone()
            
            if result is None:
                return (0, 0)
            
            total_bet = result[0] if result[0] is not None else 0
            total_win = result[1] if result[1] is not None else 0
            
            return (int(total_bet), int(total_win))

    except Exception as e:
        print(f"❌ Error in get(): {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return None

 
def delete_bet(wa_id, arr, bet_name, session, db):
    try:
        cursor = db.cursor()
        user_number = parse(wa_id)

        # Get user ID and current total_amount
        cursor.execute("SELECT id, total_bet FROM users WHERE phone_no = %s", (user_number,))
        user_result = cursor.fetchone()
        if not user_result:
            return False, f"❌ User {user_number} not found", 0

        user_id = user_result[0]
        current_user_total = user_result[1] or 0

        # Check if bet slip exists
        cursor.execute("""
            SELECT id, bets, total_amount 
            FROM bet_slips 
            WHERE user_id = %s AND event_name = %s AND bet_type = %s
        """, (user_id, bet_name, session))
        
        existing_bet = cursor.fetchone()
        
        if not existing_bet:
            return False, f"❌ No {session} bets found for {bet_name.upper()}", 0

        existing_id = existing_bet[0]
        existing_bets = json.loads(existing_bet[1]) if isinstance(existing_bet[1], str) else existing_bet[1]
        
        # Convert existing bets to ensure string keys
        current_bets = {}
        for num, amount in existing_bets.items():
            current_bets[str(num)] = int(amount)
        
        # Track deletions and calculate new totals
        deleted_bets = {}
        total_deleted = 0
        
        # Process deletions
        for num, delete_amount in arr.items():
            num_str = str(num)
            
            if num_str in current_bets:
                current_amount = current_bets[num_str]
                
                if delete_amount >= current_amount:
                    # Delete entire bet for this number
                    deleted_bets[num_str] = current_amount
                    total_deleted += current_amount
                    del current_bets[num_str]
                    print(f"DEBUG: Deleted entire bet - Number: {num_str}, Amount: ₹{current_amount}")
                    
                else:
                    # Partial deletion
                    deleted_bets[num_str] = delete_amount
                    current_bets[num_str] = current_amount - delete_amount
                    total_deleted += delete_amount
                    print(f"DEBUG: Partial deletion - Number: {num_str}, Deleted: ₹{delete_amount}, Remaining: ₹{current_bets[num_str]}")
            else:
                print(f"DEBUG: Number {num_str} not found in existing bets")

        if not deleted_bets:
            return False, f"❌ No matching bets found to delete", sum(current_bets.values())

        # Calculate new totals
        new_total_amount = sum(current_bets.values())
        new_bet_count = len(current_bets)
        
        # Update users.total_amount (subtract deleted amount)
        new_user_total = current_user_total - total_deleted
        cursor.execute("""
            UPDATE users 
            SET total_bet = %s 
            WHERE id = %s
        """, (new_user_total, user_id))

        if new_total_amount == 0:
            # Delete the entire bet slip if no bets remain
            cursor.execute("DELETE FROM bet_slips WHERE id = %s", (existing_id,))
            print(f"✅ Deleted entire bet slip: User {user_number}, Event {bet_name}, Session {session}")
            
        else:
            # Update the bet slip with remaining bets
            cursor.execute("""
                UPDATE bet_slips 
                SET bets = %s, total_amount = %s, bet_count = %s 
                WHERE id = %s
            """, (json.dumps(current_bets), new_total_amount, new_bet_count, existing_id))
            
            print(f"✅ Updated bet slip: User {user_number}, Event {bet_name}, Session {session}, Remaining: ₹{new_total_amount}")

        print(f"✅ Updated user total_amount: {current_user_total} - {total_deleted} = {new_user_total}")
        
        db.commit()
        
        # Create deletion summary
        deleted_lines = "\n".join(f"{num} = ₹{amt}" for num, amt in deleted_bets.items())
        
        success_msg = (
            f"✅ **Deleted from {bet_name.upper()} {session.upper()}:**\n"
            f"{deleted_lines}\n"
            f"💰 Deleted amount = ₹{total_deleted}\n"
            f"💰 Remaining bet total = ₹{new_total_amount}\n"
        )
        
        return True, success_msg, new_total_amount

    except Exception as e:
        db.rollback()
        print("❌ Error in delete_bet():", e)
        return False, f"❌ Failed to delete bet: {str(e)}", 0
