import datetime
import json
import os

# ===========================================
# 🕒 Event Class
# ===========================================
class Event:
    def __init__(self, event_code, ot, ct, title):
        self.EventCode = event_code
        self.OpenTime = ot
        self.CloseTime = ct
        self.title = title

    def yet_to_open(self):
        now = datetime.datetime.now().time()
        return self.OpenTime > now

    def yet_to_close(self):
        now = datetime.datetime.now().time()
        if self.yet_to_open():
            return True
        # Handle midnight crossover (close time is next day)
        if self.CloseTime < self.OpenTime:
            return now >= self.OpenTime or now < self.CloseTime
        else:
            return self.CloseTime > now

    def is_currently_open(self):
        """Check if event is currently accepting bets"""
        return not self.yet_to_open() and self.yet_to_close()


# ===========================================
# ⚙️ Event Manager Functions
# ===========================================
DEFAULT_EVENTS = {
    "de": {
        "code": "DE",
        "name": "Default Event",
        "open_time": "00:00:00",
        "close_time": "00:00:00"
    },
}

EVENTS_CONFIG_FILE = "events_config.json"

# ---------- Helper: Flexible Time Parser ----------
def parse_time_flexible(time_str):
    """Parse time in HH:MM or HH:MM:SS format"""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time format: {time_str}. Use HH:MM or HH:MM:SS")

# ===========================================
# 📄 File Operations
# ===========================================
def create_default_events_config():
    """Create default events configuration file"""
    try:
        with open(EVENTS_CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_EVENTS, f, indent=4)
        print(f"✅ Created default events config file: {EVENTS_CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error creating events config file: {e}")
        return False


def load_events_from_json():
    """Load events configuration from JSON file"""
    try:
        if not os.path.exists(EVENTS_CONFIG_FILE):
            print(f"📁 Events config file not found. Creating {EVENTS_CONFIG_FILE}...")
            create_default_events_config()
        
        with open(EVENTS_CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        events = {}
        for key, event_data in config.items():
            open_time = parse_time_flexible(event_data["open_time"])
            close_time = parse_time_flexible(event_data["close_time"])
            
            events[key] = Event(
                event_data["code"],
                open_time,
                close_time,
                event_data["name"]
            )
        
        print(f"✅ Loaded {len(events)} events from {EVENTS_CONFIG_FILE}")
        return events
        
    except Exception as e:
        print(f"❌ Error loading events from JSON: {e}")
        print(f"🔄 Using default events configuration...")
        return load_default_events()


def load_default_events():
    """Load default events if JSON loading fails"""
    events = {}
    for key, event_data in DEFAULT_EVENTS.items():
        open_time = parse_time_flexible(event_data["open_time"])
        close_time = parse_time_flexible(event_data["close_time"])
        
        events[key] = Event(
            event_data["code"],
            open_time,
            close_time,
            event_data["name"]
        )
    return events


def save_events_to_json(events):
    """Save events configuration to JSON file with debug info"""
    try:
        config = {}
        print(f"🔄 Preparing to save {len(events)} events...")
        
        for key, event in events.items():
            config[key] = {
                "code": event.EventCode,
                "name": event.title,
                "open_time": event.OpenTime.strftime("%H:%M:%S"),
                "close_time": event.CloseTime.strftime("%H:%M:%S")
            }
            print(f"📝 Event {key}: {event.EventCode} | Open: {event.OpenTime} | Close: {event.CloseTime}")
        
        with open(EVENTS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        
        if os.path.exists(EVENTS_CONFIG_FILE):
            file_size = os.path.getsize(EVENTS_CONFIG_FILE)
            print(f"✅ File saved successfully: {EVENTS_CONFIG_FILE} ({file_size} bytes)")
            with open(EVENTS_CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
            print(f"✅ Verification: File contains {len(saved_config)} events")
            for key, data in saved_config.items():
                print(f"✅ Saved {key}: {data['code']} | {data['open_time']}-{data['close_time']}")
            return True
        else:
            print(f"❌ File was not created: {EVENTS_CONFIG_FILE}")
            return False
        
    except Exception as e:
        print(f"❌ Error saving events to JSON: {e}")
        import traceback
        print(traceback.format_exc())
        return False


# ===========================================
# 🔧 Event Management
# ===========================================
def update_event_timing(events, event_code, open_time=None, close_time=None):
    """Update event timing and save to JSON"""
    try:
        event_code = event_code.lower()
        
        if event_code not in events:
            return False, f"❌ Event '{event_code.upper()}' not found. Available: {list(events.keys())}"
        
        event = events[event_code]
        
        if open_time:
            try:
                old_open_time = event.OpenTime
                new_open_time = parse_time_flexible(open_time)
                event.OpenTime = new_open_time
                print(f"✅ Updated {event.EventCode} open time: {old_open_time} → {new_open_time}")
            except ValueError as ve:
                return False, str(ve)
        
        if close_time:
            try:
                old_close_time = event.CloseTime
                new_close_time = parse_time_flexible(close_time)
                event.CloseTime = new_close_time
                print(f"✅ Updated {event.EventCode} close time: {old_close_time} → {new_close_time}")
            except ValueError as ve:
                return False, str(ve)
        
        if save_events_to_json(events):
            return True, f"✅ {event.EventCode} timing updated successfully and saved"
        else:
            return False, f"❌ Failed to save changes"
            
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return False, f"❌ Error updating event timing: {e}"


# ===========================================
# 🧩 Event Status & Commands
# ===========================================
def get_events_status(events):
    """Get current status of all events"""
    try:
        now = datetime.datetime.now().time()
        status_lines = []
        
        for code, event in events.items():
            if event.yet_to_open():
                status = f"⏳ Opens at {event.OpenTime.strftime('%H:%M:%S')}"
            elif event.yet_to_close():
                status = f"🟢 OPEN - Closes at {event.CloseTime.strftime('%H:%M:%S')}"
            else:
                status = f"🔴 CLOSED"
            
            status_lines.append(f"**{event.EventCode} ({event.title}):** {status}")
        
        current_time = datetime.datetime.now().strftime('%H:%M:%S')
        return f"🕐 **Current Time:** {current_time}\n\n" + "\n".join(status_lines)
        
    except Exception as e:
        return f"❌ Error getting events status: {e}"


def admin_update_event_command(events, command_text):
    """Process admin commands for updating events"""
    try:
        parts = command_text.lower().strip().split()
        
        if not parts:
            return get_events_help_message()
        
        command = parts[0]
        
        if command == "status":
            return get_events_status(events)
        
        elif command == "reload":
            new_events = load_events_from_json()
            events.clear()
            events.update(new_events)
            reload_events()
            return f"🔄 Events reloaded from JSON file"
        
        elif command == "save":
            if save_events_to_json(events):
                return "✅ Events manually saved"
            else:
                return "❌ Failed to save"
        
        elif command == "debug":
            debug_info = f"🔍 DEBUG INFO\n\n"
            debug_info += f"File: {EVENTS_CONFIG_FILE}\nExists: {os.path.exists(EVENTS_CONFIG_FILE)}\n"
            if os.path.exists(EVENTS_CONFIG_FILE):
                file_size = os.path.getsize(EVENTS_CONFIG_FILE)
                debug_info += f"File size: {file_size} bytes\n"
            debug_info += f"Events loaded: {len(events)}\n\n"
            for key, event in events.items():
                debug_info += f"{key}: {event.EventCode} | {event.OpenTime}-{event.CloseTime}\n"
            return debug_info
        
        elif command == "update":
            if len(parts) < 4:
                return "❌ Invalid format. Use: update <event> <open/close> <time>"
            
            event_code = parts[1]
            open_time = None
            close_time = None
            
            i = 2
            while i < len(parts) - 1:
                if parts[i] == "open" and i + 1 < len(parts):
                    open_time = parts[i + 1]
                    i += 2
                elif parts[i] == "close" and i + 1 < len(parts):
                    close_time = parts[i + 1]
                    i += 2
                else:
                    i += 1
            
            success, message = update_event_timing(events, event_code, open_time, close_time)
            if success:
                reload_events()
            return message
        
        elif command == "help":
            return get_events_help_message()
        
        else:
            return f"❌ Unknown command: {command}\n\n{get_events_help_message()}"
            
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"❌ Error processing admin command: {e}"


# ===========================================
# 🧭 Helper Messages
# ===========================================
def get_events_help_message():
    return """🔧 **ADMIN EVENT COMMANDS**

**📊 Status & Info:**
• `events status`
• `events reload`
• `events debug`
• `events save`

**⏰ Update Timings:**
• `events update <event> open <HH:MM[:SS]>`
• `events update <event> close <HH:MM[:SS]>`
• `events update <event> open <time> close <time>`

**📝 Examples:**
• `events update bd open 12:00`
• `events update kn close 23:15:30`
• `events update bd open 11:30 close 13:30:45`

Supports both HH:MM and HH:MM:SS formats."""

# ===========================================
# 🚀 Initialize Global Events
# ===========================================
events = load_events_from_json()

def reload_events():
    """Reload global events"""
    global events
    print(f"🔄 Reloading global events...")
    events = load_events_from_json()
    print(f"✅ Reloaded {len(events)} events")
    return events
