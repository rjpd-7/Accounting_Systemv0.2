# Hybrid Account Code Generation Guide

## Overview
This system combines **AJAX** and **WebSocket** technologies to provide real-time account code updates while preventing duplicates when multiple users create accounts simultaneously.

## How It Works

### 1. **AJAX Preview** (Fast Individual Updates)
- When a user opens the "Create Account" modal or changes account type
- JavaScript sends AJAX request to `/api/next_account_code/?type=<account_type>`
- Server returns next available code instantly
- Updates user's preview field immediately

### 2. **WebSocket Live Updates** (Cross-User Synchronization)
- All users connect to `ws://localhost:8000/ws/account-codes/` on page load
- When **any user** successfully creates an account:
  - Server broadcasts to all connected users via WebSocket
  - Each user's preview automatically updates if viewing same account type
  - Status indicator shows 🟢 **Live** when WebSocket is connected, 🟡 **AJAX Only** when disconnected

### 3. **Database Atomic Finalization** (Duplicate Prevention)
- When account is submitted, server uses `select_for_update()` row-level lock
- Atomic transaction ensures only one code is generated at exact moment
- If rare duplicate occurs, retry mechanism attempts 3 times
- Final code may differ from preview if another user submitted first

## Flow Diagram

```
User A Opens Modal → AJAX fetch → Preview: 100005
User B Opens Modal → AJAX fetch → Preview: 100005 (same!)

User A Submits → Server atomic lock → Creates 100005 → Broadcast
                                                           ↓
User B Preview ← WebSocket update ← Receives next code (100006)

User B Submits → Server atomic lock → Creates 100006 → No duplicate!
```

## Technical Components

### Frontend
- **File**: `static/scripts/account_code_hybrid.js`
- **CSS**: `static/styles/account_code_hybrid.css`
- **Class**: `HybridAccountCodeManager`
- **Methods**:
  - `connectWebSocket()` - Establishes WebSocket connection
  - `fetchPreviewCode()` - AJAX request for next code
  - `handleAccountCreated()` - WebSocket event handler for broadcasts

### Backend
- **Views**: `views.py`
  - `get_next_account_code()` - Thread-safe code generation (lines 76-110)
  - `create_account()` - Atomic creation + WebSocket broadcast (lines 1032-1095)
- **Consumer**: `consumers.py` - `AccountCodeConsumer` class
- **Routing**: `routing.py` - `ws/account-codes/` WebSocket route

### Database Safety
- **Locking**: `select_for_update()` prevents race conditions
- **Atomicity**: `transaction.atomic()` ensures all-or-nothing operations
- **Retry**: `IntegrityError` handler retries up to 3 times

## Status Indicators

| Symbol | Status | Meaning |
|--------|--------|---------|
|  🟢 | **Live** | Both AJAX and WebSocket active, real-time updates enabled |
| 🟡 | **AJAX Only** | WebSocket disconnected, using AJAX fallback |

## Benefits

1. **Prevents Duplicates**: Database-level locking ensures unique codes
2. **Fast Preview**: AJAX provides instant response for user's own preview
3. **Cross-User Updates**: WebSocket broadcasts keep all users synchronized
4. **Graceful Degradation**: Works with AJAX alone if WebSocket fails
5. **Visual Feedback**: Animation highlights when code changes due to another user's action

## Testing Multi-User Scenario

### Manual Test:
1. Open accounts page in two different browsers (e.g., Chrome and Firefox)
2. Log in as different users in each browser
3. In both browsers, open "Create Account" modal
4. Select same account type (e.g., Assets) in both
5. Both should show same preview code (e.g., 100005)
6. Verify status shows 🟢 **Live** in both browsers
7. In Browser 1, submit the account
8. **Expected**: Browser 2's preview automatically updates to next code (100006) with highlight animation
9. Submit account in Browser 2
10. **Expected**: Account created successfully with code 100006 (no duplicate error)

## Troubleshooting

- **WebSocket won't connect**: Check Daphne is running, not Django's development server
- **Both previews don't match**: This is OK! Final code is assigned atomically on submit
- **Duplicate error appears**: Retry mechanism should handle this automatically (check logs for retry messages)
- **Preview doesn't update after other user creates**: Check browser console for WebSocket errors

## Configuration

No additional configuration needed. System automatically:
- Detects WebSocket availability
- Falls back to AJAX-only if WebSocket fails
- Uses in-memory channel layer for broadcasts
- Generates codes based on account type (100000s for Assets, 200000s for Liabilities, etc.)
