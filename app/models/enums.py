from enum import Enum


class OrderStatuses(str, Enum):
    created = "created"
    paid = "paid"
    completed = "completed"
    cancelled = "cancelled"
