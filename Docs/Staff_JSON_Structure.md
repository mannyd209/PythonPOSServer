# Staff JSON Structure

## Purpose:
- Manages staff details, including login credentials, pay rate, and work status.
- Tracks whether staff members are **working**, **on break**, or **clocked out**.

## JSON Structure for Staff:
```json
{
  "staff": [
    {
      "name": "Staff Member Name",
      "pin": 0000,
      "hourly_rate": 0.00,
      "isAdmin": false,
      "working": false,
      "break": false
    }
  ]
}
```

---

## Fields Explanation:

| Field          | Type      | Description |
|---------------|----------|-------------|
| `name`        | `string`  | Name of the staff member. |
| `pin`         | `integer` | Login PIN for accessing the system. |
| `hourly_rate` | `float`   | Hourly pay rate of the staff member. |
| `isAdmin`     | `boolean` | Whether the staff member has admin access (**default: false**). |
| `working`     | `boolean` | **True** if the staff member is clocked in and working, **False** otherwise. |
| `break`       | `boolean` | **True** if the staff member is currently on break, **False** otherwise. |

---

## How Work Status is Tracked:

1. **Clocked Out (Not Working)**  
   ```json
   { "working": false, "break": false }
   ```

2. **Clocked In (Working)**  
   ```json
   { "working": true, "break": false }
   ```

3. **On Break**  
   ```json
   { "working": false, "break": true }
   ```

4. **Returning from Break (Back to Work)**  
   ```json
   { "working": true, "break": false }
   ```

---

## Why This Works Well:
✅ **Simple and Efficient** - Only two fields needed to track work status.  
✅ **Clear State Changes** - Easy to update when staff **clock in, take a break, or clock out**.  
✅ **Scalable** - Can be expanded in the future if needed.  

This setup makes it easy to track **staff attendance and activity** in real time! 🚀  
