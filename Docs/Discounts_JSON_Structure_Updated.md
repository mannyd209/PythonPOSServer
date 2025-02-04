# Discounts JSON Structure

## Purpose:
- Creates a `discount_group` instead of treating discounts as items.
- **Admins** can toggle the entire **discount group ON/OFF**.
- Each **individual discount** inside the `discount_group` has:
  - **Name**
  - **Amount to subtract (flat amount) or percentage discount**
  - **Sort order**
  - **Available toggle**
  - **isPercentage (boolean)**: Determines if the discount applies as a percentage (`true`) or as a flat amount (`false`).

## JSON Structure for Discounts:
```json
{
  "discount_group": [
    {
      "name": "Discounts",
      "discount_group_id": 999999,
      "available": true,
      "sort_order": 000000,
      "discounts": [
        {
          "name": "10% Off",
          "amount": 10.00,
          "isPercentage": true,
          "sort_order": 000001,
          "available": true
        },
        {
          "name": "Flat $5 Off",
          "amount": -5.00,
          "isPercentage": false,
          "sort_order": 000002,
          "available": true
        },
        {
          "name": "Holiday Special 15%",
          "amount": 15.00,
          "isPercentage": true,
          "sort_order": 000003,
          "available": false
        }
      ]
    }
  ]
}
```

---

## Fields Explanation

### Discount Group (`discount_group` array)
| Field | Type | Description |
|--------|------|-------------|
| `name` | `string` | Name of the discount group (**always "Discounts"**). |
| `discount_group_id` | `integer` | **Always `999999`**, uniquely identifying this group. |
| `available` | `boolean` | **Admins can toggle ALL discounts ON/OFF** (`true/false`). |
| `sort_order` | `integer` | Determines the display order of the discount group. |
| `discounts` | `array` | **Holds individual discounts** inside this group. |

### Individual Discounts (`discounts` array inside `discount_group`)
| Field | Type | Description |
|--------|------|-------------|
| `name` | `string` | Name of the discount (e.g., "10% Off"). |
| `amount` | `float` | **Value of the discount** (negative if it's a flat amount, positive if percentage). |
| `isPercentage` | `boolean` | **True** if the discount applies as a percentage, **False** if it's a flat amount. |
| `sort_order` | `integer` | Determines display order of this discount in the list. |
| `available` | `boolean` | **Admins can toggle individual discounts ON/OFF** (`true/false`). |

---

## How This Works

1. **Discount Group (`discount_group`)**
   - Functions as a **mod list** but for discounts.
   - If `available: false`, **ALL** discounts inside become **inactive**.

2. **Individual Discounts (`discounts` array)**
   - Each discount can be toggled ON/OFF (`available: true/false`).
   - **Two types of discounts**:
     - **Flat Amount Discounts** (negative value, e.g., `-5.00` for $5 off).
     - **Percentage Discounts** (positive value, e.g., `10.00` for 10% off, with `isPercentage: true`).
   - **Sort order** controls display order.

---

## Why This Works Well

✅ **Gives flexibility** for both percentage-based and flat amount discounts.  
✅ **Keeps discounts structured separately** from categories/items.  
✅ **Easy to manage** entire discount groups or individual discounts.  
✅ **Scalable** if more discount groups are needed in the future.  

This setup makes it **super clean for your backend developer** while allowing full control over discounts. 🚀  
