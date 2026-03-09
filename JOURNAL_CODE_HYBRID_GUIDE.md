# Real-Time Journal Code Generation Guide

## Overview
This system applies the same **hybrid AJAX + WebSocket** approach to journal code generation as the account code system, providing real-time journal code updates while preventing duplicates when multiple users create journals simultaneously.

## How It Works

### 1. **AJAX Preview** (Fast Individual Updates)
- When a user opens the "Add New Journal" modal
- JavaScript sends AJAX request to `/api/next_journal_code/`
- Server returns next available code instantly (format: `JE-0000000001`)
- Updates user's preview field immediately

### 2. **WebSocket Live Updates** (Cross-User Synchronization)
- All users connect to `ws://localhost:8000/ws/journal-codes/` on page load
- When **any user** successfully creates a journal:
  - Server broadcasts to all connected users via WebSocket
  - Each user's preview automatically updates with the new next code
  - Status indicator shows 🟢 **Live** when WebSocket is connected, 🟡 **AJAX Only** when disconnected

### 3. **Database Atomic Finalization** (Duplicate Prevention)
- `get_next_journal_code()` uses `select_for_update()` row-level lock
- Atomic transaction ensures only one code is generated at exact moment
- If rare duplicate occurs, the system handles it gracefully
- Final code is assigned atomically immediately after successful journal creation

## Flow Diagram

```
User A Opens Modal → AJAX fetch → Preview: JE-0000000001
User B Opens Modal → AJAX fetch → Preview: JE-0000000001 (same!)

User A Submits → Server atomic lock → Creates JE-0000000001 → Broadcast
                                                                   ↓
User B Preview ← WebSocket update ← Receives next code (JE-0000000002)

User B Submits → Server atomic lock → Creates JE-0000000002 → No duplicate!
```

## Technical Components

### Frontend
- **File**: `static/scripts/journal_code_hybrid.js`
- **CSS**: `static/styles/journal_code_hybrid.css`
- **Class**: `HybridJournalCodeManager`
- **Methods**:
  - `connectWebSocket()` - Establishes WebSocket connection to `ws/journal-codes/`
  - `fetchPreviewCode()` - AJAX request to `/api/next_journal_code/`
  - `handleJournalCreated()` - WebSocket event handler for broadcasts

### Backend
- **Views**: `views.py`
  - `get_next_journal_code()` (lines 137-168) - Thread-safe journal code generation with `select_for_update()`
  - `get_next_journal_code_api()` (lines 182-186) - AJAX endpoint returning JSON
  - `insert_journals()` (lines 1568-1678) - Atomic journal creation + WebSocket broadcast
  
- **Consumer**: `consumers.py` - `JournalCodeConsumer` class
  - Listens on `journal_code_updates` channel
  - Broadcasts `journal_created` events to all connected clients
  
- **Routing**: `routing.py` - WebSocket route `ws/journal-codes/` pointing to JournalCodeConsumer

### Database Safety
- **Locking**: `select_for_update()` on both JournalHeaderDrafts and JournalHeader tables prevents race conditions
- **Atomicity**: `transaction.atomic()` ensures all-or-nothing operations
- **Format**: Codes are zero-padded 10-digit numbers (e.g., `JE-0000000001`)

## Status Indicators

| Symbol | Status | Meaning |
|--------|--------|---------|
| 🟢 | **Live** | Both AJAX and WebSocket active, real-time updates enabled |
| 🟡 | **AJAX Only** | WebSocket disconnected, using AJAX fallback |

## Benefits

1. **Prevents Duplicates**: Database-level locking ensures unique codes
2. **Fast Preview**: AJAX provides instant response for user's own preview
3. **Cross-User Updates**: WebSocket broadcasts keep all users synchronized
4. **Graceful Degradation**: Works with AJAX alone if WebSocket fails
5. **Visual Feedback**: Animation highlights when code changes due to another user's action

## Testing Multi-User Scenario

### Manual Test:
1. **Setup**: Ensure Daphne is running (`python -m daphne -b 127.0.0.1 -p 8000 Accounting_System.asgi:application`)
2. **Open** journal page in two different browsers (Chrome + Firefox)
3. **Log in** as different users in each browser
4. **Click** "Add New Journal" button in both browsers
5. Both should preview same code (e.g., `JE-0000000001`)
6. **Verify** status shows 🟢 **Live** in both browsers
7. In Browser 1, **submit** the journal entry form
8. **Expected**: Browser 2's preview automatically updates to next code (`JE-0000000002`) with animation
9. In Browser 2, **submit** the journal entry
10. **Expected**: Journal created successfully with code `JE-0000000002` (no duplicate error)

## Testing: Comparing Both Systems

### Before (Without Real-Time)
- User A creates journal → No notification to User B
- User B might attempt same journal code → Potential logic errors
- Requires manual page refresh to see updates

### After (With Hybrid AJAX+WebSocket)
- User A creates journal → Instant broadcast to all users
- User B's preview code auto-updates in real-time
- No manual refresh needed, true real-time collaboration

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Only shows 🟡 AJAX Only | Daphne not running | Use `python -m daphne -b 127.0.0.1 -p 8000 Accounting_System.asgi:application` |
| Preview codes don't match across users | Normal! | Database lock ensures final codes are unique |
| Preview doesn't update after other user creates | WebSocket error | Check browser console for error messages |
| Duplicate journal code error | Failed broadcast | Retry mechanism should handle this; check server logs |

## Configuration

No additional configuration needed. System automatically:
- Detects WebSocket availability
- Falls back to AJAX-only if WebSocket fails
- Uses in-memory channel layer for broadcasts
- Generates codes with format `JE-` + 10-digit zero-padded number

## Relationship to Account Code System

Both systems (journal and account code generation) use identical principles:
- **Same architecture**: AJAX + WebSocket hybrid
- **Same database safety**: `select_for_update()` for atomic locking
- **Same UI patterns**: Status indicator and highlight animation
- **Same reliability**: Graceful fallback to AJAX if WebSocket unavailable

The main differences:
- **Account codes**: `/api/next_account_code/`, `ws/account-codes/`, format varies by type (100000s, 200000s, etc.)
- **Journal codes**: `/api/next_journal_code/`, `ws/journal-codes/`, format always `JE-XXXXXXXXXX`

## Files Modified

1. `views.py`
   - Updated `get_next_journal_code()` with atomic locking
   - Updated `insert_journals()` with WebSocket broadcast

2. `consumers.py`
   - Added `JournalCodeConsumer` class

3. `routing.py`
   - Added WebSocket route for journal codes

4. `static/scripts/journal_code_hybrid.js`
   - New: Hybrid manager class

5. `static/styles/journal_code_hybrid.css`
   - New: Styling for status indicator and animations

6. `templates/Front_End/journal.html`
   - Added CSS link and JS script
   - Updated journal code input with status indicator

7. `templates/Student/journal.html`
   - Same updates as Front_End version
